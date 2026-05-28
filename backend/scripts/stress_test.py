#!/usr/bin/env python3
"""
Dental AI Backend — Hard Stress Test Suite
==========================================
Scenarios
  A  Login storm            – auth throughput, latency distribution, error rate
  B  Appointment booking race  – concurrent double-booking, cancel/rebook integrity
  C  Patient creation + lookup – duplicate detection, search consistency
  D  Mixed traffic soak        – sustained load across all endpoints

Usage
  python stress_test.py                         # run all scenarios
  python stress_test.py --scenarios A,B         # specific scenarios
  python stress_test.py --cleanup               # delete test data after run
  python stress_test.py --scenarios D --duration 600 --concurrency 100

Env-var overrides (same names as CLI args, uppercase)
  BASE_URL          https://dental-ai-backend-244697312574.us-west1.run.app
  ADMIN_EMAIL       admin@dentalai.test
  ADMIN_PASSWORD    DentalAI2026!
  PRACTICE_ID       practice-test-001
  CONCURRENCY       50
  SOAK_DURATION     120          seconds
  LOGIN_WORKERS     50
  BOOKING_WORKERS   150
  PATIENT_COUNT     300
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

BASE_URL         = os.getenv("BASE_URL",         "https://dental-ai-backend-244697312574.us-west1.run.app")
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL",      "admin@dentalai.test")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD",   "DentalAI2026!")
PRACTICE_ID      = os.getenv("PRACTICE_ID",      "practice-test-001")
CONCURRENCY      = int(os.getenv("CONCURRENCY",      "50"))
SOAK_DURATION    = int(os.getenv("SOAK_DURATION",    "120"))
LOGIN_WORKERS    = int(os.getenv("LOGIN_WORKERS",    "50"))
BOOKING_WORKERS  = int(os.getenv("BOOKING_WORKERS",  "150"))
PATIENT_COUNT    = int(os.getenv("PATIENT_COUNT",    "300"))

# ── Test-data markers ────────────────────────────────────────────────────────
# All load-test records are tagged so cleanup never touches seed data.
LOAD_TAG          = "LOAD_TEST"
LT_EMAIL_SUFFIX   = "+loadtest@stress.test"
LT_PHONE_PREFIX   = "+1555900"   # reserved range: +15559000000 – +15559009999

# Seed provider IDs from init_db.py — never deleted by cleanup
SEED_PROVIDERS = [
    "provider-sarah-lee-001",
    "provider-michael-chen-001",
    "provider-emily-rogers-001",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Structured logging (JSON-lines to stdout)
# ═══════════════════════════════════════════════════════════════════════════════

class _JsonFmt(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        d: dict = {
            "ts":  datetime.now(timezone.utc).isoformat(),
            "lvl": r.levelname,
            "msg": r.getMessage(),
        }
        if isinstance(r.args, dict):
            d.update(r.args)
            r.args = None           # prevent double-formatting
        return json.dumps(d, default=str)

_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(_JsonFmt())
log = logging.getLogger("stress")
log.addHandler(_h)
log.setLevel(logging.INFO)
log.propagate = False


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════════════

class Metrics:
    """Thread-/coroutine-safe per-endpoint latency + status counters."""

    def __init__(self) -> None:
        self._lat:  Dict[str, List[float]]       = defaultdict(list)
        self._cnt:  Dict[str, int]               = defaultdict(int)
        self._err:  Dict[str, int]               = defaultdict(int)
        self._sc:   Dict[str, Dict[int, int]]    = defaultdict(lambda: defaultdict(int))
        self._lock  = asyncio.Lock()

    async def record(self, label: str, status: int, elapsed_s: float) -> None:
        async with self._lock:
            self._lat[label].append(elapsed_s * 1000)
            self._cnt[label] += 1
            self._sc[label][status] += 1
            if status == 0 or status >= 400:
                self._err[label] += 1

    def _pct(self, data: List[float], p: float) -> float:
        if not data:
            return 0.0
        s = sorted(data)
        return round(s[min(int(len(s) * p), len(s) - 1)], 1)

    def print_summary(self) -> None:
        width = 70
        print("\n" + "═" * width)
        print("  PERFORMANCE SUMMARY")
        print("═" * width)
        for label in sorted(self._lat):
            lats  = self._lat[label]
            total = self._cnt[label]
            errs  = self._err.get(label, 0)
            erate = 100 * errs / max(total, 1)
            print(f"\n  {label}")
            print(f"    requests : {total}")
            print(f"    errors   : {errs}  ({erate:.1f}%)")
            print(f"    statuses : {dict(sorted(self._sc[label].items()))}")
            print(f"    p50/p95/p99 ms : "
                  f"{self._pct(lats,.50)} / {self._pct(lats,.95)} / {self._pct(lats,.99)}")
            print(f"    min/max ms     : "
                  f"{self._pct(lats,0):.1f} / {self._pct(lats,1.0):.1f}")

METRICS = Metrics()


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP client helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _client(token: Optional[str] = None) -> httpx.AsyncClient:
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(
        base_url=BASE_URL,
        headers=hdrs,
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
    )


async def req(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    label: str,
    *,
    body:   Optional[dict] = None,
    params: Optional[dict] = None,
    retries: int = 2,
) -> Tuple[Optional[httpx.Response], float]:
    """Execute a request, record metrics, retry on transient network errors."""
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            resp = await client.request(method, path, json=body, params=params)
            elapsed = time.perf_counter() - t0
            await METRICS.record(label, resp.status_code, elapsed)
            return resp, elapsed
        except (httpx.ConnectError, httpx.TimeoutException,
                httpx.RemoteProtocolError, httpx.ReadError) as exc:
            elapsed = time.perf_counter() - t0
            await METRICS.record(label, 0, elapsed)
            if attempt < retries:
                await asyncio.sleep(0.4 * (attempt + 1))
            else:
                log.warning("net_error %s", {"label": label, "error": str(exc)})
                return None, elapsed
    return None, 0.0


async def login(email: str, password: str) -> Optional[str]:
    async with _client() as c:
        resp, _ = await req(
            c, "POST", "/api/auth/login", "POST /api/auth/login",
            body={"email": email, "password": password},
        )
    if resp and resp.status_code == 200:
        return resp.json().get("access_token")
    return None


async def bootstrap() -> Tuple[str, List[dict], dict]:
    """Authenticate, load providers and baseline practice config."""
    token = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not token:
        log.error("bootstrap_login_failed %s", {"email": ADMIN_EMAIL})
        sys.exit(1)
    log.info("bootstrap_auth_ok %s", {"email": ADMIN_EMAIL})

    async with _client(token) as c:
        prov_r, _ = await req(c, "GET", "/api/providers", "GET /api/providers")
        cfg_r, _  = await req(
            c, "GET", f"/api/practice/{PRACTICE_ID}/config",
            "GET /api/practice/{id}/config",
        )

    providers = prov_r.json() if prov_r and prov_r.status_code == 200 else []
    cfg_before = cfg_r.json() if cfg_r  and cfg_r.status_code  == 200 else {}
    log.info("bootstrap_ok %s", {"providers": len(providers)})
    return token, providers, cfg_before


# ═══════════════════════════════════════════════════════════════════════════════
# Test-data generators
# ═══════════════════════════════════════════════════════════════════════════════

def lt_phone(n: int) -> str:
    return f"{LT_PHONE_PREFIX}{n:04d}"

def lt_email(n: int) -> str:
    return f"stress{n:05d}{LT_EMAIL_SUFFIX}"

def next_weekday(offset_days: int = 1) -> str:
    """Return a YYYY-MM-DD that is at least offset_days away and is Mon–Fri."""
    d = datetime.now(timezone.utc).date() + timedelta(days=offset_days)
    while d.weekday() >= 5:          # skip Sat/Sun
        d += timedelta(days=1)
    return d.isoformat()

def rand_slot(hour_start: int = 9, hour_end: int = 11) -> str:
    """Random :00 or :30 slot within [hour_start, hour_end)."""
    return f"{random.randint(hour_start, hour_end - 1):02d}:{random.choice([0, 30]):02d}"


# ═══════════════════════════════════════════════════════════════════════════════
# Assertion helpers — violations collected here, checked at the end
# ═══════════════════════════════════════════════════════════════════════════════

VIOLATIONS: List[str] = []

def _vio(scenario: str, rule: str, detail: str) -> None:
    msg = f"[{scenario}] {rule}: {detail}"
    VIOLATIONS.append(msg)
    log.warning("violation %s", {"scenario": scenario, "rule": rule, "detail": detail})


def check_no_double_bookings(scenario: str, appointments: List[dict]) -> None:
    """No two active appointments may share (provider_id, date, time)."""
    seen: Dict[tuple, str] = {}
    for apt in appointments:
        if apt.get("status") in {"cancelled", "no_show"}:
            continue
        key = (apt.get("provider_id"), apt.get("appointment_date"), apt.get("appointment_time"))
        if None in key:
            continue
        if key in seen:
            _vio(scenario, "DOUBLE_BOOKING",
                 f"provider={key[0]} {key[1]}@{key[2]} "
                 f"ids=[{seen[key]}, {apt['id']}]")
        else:
            seen[key] = apt["id"]


def check_valid_statuses(scenario: str, appointments: List[dict]) -> None:
    valid = {"pending_verification", "pending_review", "scheduled",
             "completed", "cancelled", "no_show"}
    for apt in appointments:
        s = apt.get("status")
        if s not in valid:
            _vio(scenario, "INVALID_STATUS",
                 f"id={apt.get('id')} status={s!r}")


def check_referential_integrity(
    scenario: str,
    appointments: List[dict],
    patient_ids: set,
    provider_ids: set,
) -> None:
    for apt in appointments:
        if apt.get("status") == "cancelled":
            continue
        pid  = apt.get("patient_id")
        prov = apt.get("provider_id")
        if pid and pid not in patient_ids:
            _vio(scenario, "ORPHAN_PATIENT_REF",
                 f"apt={apt.get('id')} patient_id={pid}")
        if prov and prov not in provider_ids:
            _vio(scenario, "ORPHAN_PROVIDER_REF",
                 f"apt={apt.get('id')} provider_id={prov}")


def check_settings_immutable(
    scenario: str,
    before: dict,
    after: dict,
    keys: List[str] = None,
) -> None:
    for k in (keys or ["practice_id", "name", "default_timezone"]):
        if before.get(k) != after.get(k):
            _vio(scenario, "SETTINGS_MUTATED",
                 f"key={k!r} before={before.get(k)!r} after={after.get(k)!r}")


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO A — Login storm
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_a(n: int = LOGIN_WORKERS) -> None:
    log.info("scenario_a_start %s", {"workers": n})
    sem = asyncio.Semaphore(min(n, 100))
    results: Dict[str, int] = defaultdict(int)
    lock = asyncio.Lock()

    async def worker(_: int) -> None:
        async with sem:
            token = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
        async with lock:
            if token:
                results["ok"] += 1
            else:
                results["fail"] += 1

    await asyncio.gather(*[worker(i) for i in range(n)])
    log.info("scenario_a_done %s", {
        **results,
        "success_pct": round(100 * results["ok"] / max(n, 1), 1),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO B — Appointment booking race
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_b(token: str, providers: List[dict], n: int = BOOKING_WORKERS) -> None:
    log.info("scenario_b_start %s", {"workers": n})

    # Pick the first seeded provider that exists in the DB response
    prov_ids = {p["id"] for p in providers}
    provider_id = next(
        (pid for pid in SEED_PROVIDERS if pid in prov_ids),
        (providers[0]["id"] if providers else None),
    )
    if not provider_id:
        log.warning("scenario_b_skipped %s", {"reason": "no providers"})
        return

    date_str = next_weekday(2)      # two days out to avoid seeded appointments
    log.info("scenario_b_target %s", {"provider": provider_id, "date": date_str})

    # Pre-create/find a throwaway patient for this scenario
    patient_id: Optional[str] = None
    async with _client(token) as c:
        resp, _ = await req(
            c, "POST", "/api/patients", "POST /api/patients",
            body={
                "name":  f"{LOAD_TAG} Race Patient",
                "phone": lt_phone(0),
                "email": f"race{LT_EMAIL_SUFFIX}",
                "notes": LOAD_TAG,
            },
        )
        if resp and resp.status_code == 200:
            patient_id = resp.json()["id"]
        elif resp and resp.status_code == 409:
            detail = resp.json().get("detail", {})
            patient_id = (detail.get("patient") or {}).get("id") if isinstance(detail, dict) else None

    if not patient_id:
        log.warning("scenario_b_skipped %s", {"reason": "could not create race patient"})
        return

    # ── Wave 1: N workers race to book 4 possible slots ─────────────────────
    # Only 4 distinct slots → massive collision pressure
    sem = asyncio.Semaphore(min(n, 200))
    created_ids:  List[str] = []
    results = defaultdict(int)
    lock = asyncio.Lock()

    async def book_worker(wid: int) -> None:
        async with sem:
            slot = rand_slot(9, 11)          # 09:00 / 09:30 / 10:00 / 10:30
            async with _client(token) as c:
                resp, _ = await req(
                    c, "POST", "/api/appointments", "POST /api/appointments",
                    body={
                        "patient_id":       patient_id,
                        "patient_name":     f"{LOAD_TAG} Race Patient",
                        "patient_phone":    lt_phone(0),
                        "appointment_date": date_str,
                        "appointment_time": slot,
                        "service_type":     "cleaning",
                        "duration_minutes": 30,
                        "provider_id":      provider_id,
                        "notes":            f"{LOAD_TAG} race wid={wid}",
                    },
                )
        async with lock:
            if resp and resp.status_code == 200:
                results["created"] += 1
                aid = resp.json().get("id")
                if aid:
                    created_ids.append(aid)
            elif resp and resp.status_code == 409:
                results["conflict_409"] += 1
            else:
                results["other_error"] += 1

    await asyncio.gather(*[book_worker(i) for i in range(n)])
    log.info("scenario_b_wave1 %s", {**results, "ids": len(created_ids)})

    # ── Wave 2: cancel first half, immediately rebook ─────────────────────
    half = created_ids[: len(created_ids) // 2]

    async def cancel_rebook(appt_id: str, wid: int) -> None:
        async with sem:
            async with _client(token) as c:
                await req(
                    c, "DELETE", f"/api/appointments/{appt_id}",
                    "DELETE /api/appointments/{id}",
                )
            async with _client(token) as c:
                await req(
                    c, "POST", "/api/appointments", "POST /api/appointments",
                    body={
                        "patient_id":       patient_id,
                        "patient_name":     f"{LOAD_TAG} Race Patient",
                        "patient_phone":    lt_phone(0),
                        "appointment_date": date_str,
                        "appointment_time": rand_slot(9, 11),
                        "service_type":     "cleaning",
                        "duration_minutes": 30,
                        "provider_id":      provider_id,
                        "notes":            f"{LOAD_TAG} rebook wid={wid}",
                    },
                )

    await asyncio.gather(*[cancel_rebook(aid, i) for i, aid in enumerate(half)])

    # ── Post-race assertions ────────────────────────────────────────────────
    await asyncio.sleep(1)      # allow in-flight writes to settle
    async with _client(token) as c:
        resp, _ = await req(
            c, "GET", "/api/appointments", "GET /api/appointments",
            params={"provider_id": provider_id},
        )
    all_for_prov = resp.json() if resp and resp.status_code == 200 else []
    lt_apts = [a for a in all_for_prov if LOAD_TAG in (a.get("notes") or "")]

    check_no_double_bookings("B", lt_apts)
    check_valid_statuses("B", lt_apts)

    log.info("scenario_b_done %s", {
        **results,
        "lt_appointments": len(lt_apts),
        "violations": len(VIOLATIONS),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO C — Patient creation + lookup
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_c(token: str, n: int = PATIENT_COUNT) -> None:
    log.info("scenario_c_start %s", {"n_patients": n})
    sem   = asyncio.Semaphore(CONCURRENCY)
    lock  = asyncio.Lock()
    created: List[dict] = []
    results: Dict[str, int] = defaultdict(int)

    # ── Concurrent creates ──────────────────────────────────────────────────
    async def create_worker(i: int) -> None:
        async with sem:
            phone = lt_phone(1000 + i)
            email = lt_email(i)
            async with _client(token) as c:
                resp, _ = await req(
                    c, "POST", "/api/patients", "POST /api/patients",
                    body={
                        "name":          f"{LOAD_TAG} Patient {i:05d}",
                        "phone":         phone,
                        "email":         email,
                        "date_of_birth": "1990-03-22",
                        "notes":         LOAD_TAG,
                    },
                )
        async with lock:
            if resp and resp.status_code == 200:
                results["created"] += 1
                created.append({"id": resp.json()["id"], "phone": phone, "email": email})
            elif resp and resp.status_code == 409:
                results["dup_409"] += 1
            else:
                results["error"] += 1

    await asyncio.gather(*[create_worker(i) for i in range(n)])
    log.info("scenario_c_creates %s", dict(results))

    # ── Concurrent lookups on a sample of freshly created patients ─────────
    sample   = random.sample(created, min(60, len(created)))
    ok_lock  = asyncio.Lock()
    lu_ok = 0
    lu_fail = 0

    async def lookup_worker(p: dict) -> None:
        nonlocal lu_ok, lu_fail
        async with sem:
            async with _client(token) as c:
                resp, _ = await req(
                    c, "GET", f"/api/patients/{p['id']}", "GET /api/patients/{id}",
                )
        async with ok_lock:
            if resp and resp.status_code == 200:
                data = resp.json()
                if data.get("phone") == p["phone"] and data.get("email") == p["email"]:
                    lu_ok += 1
                else:
                    lu_fail += 1
                    _vio("C", "LOOKUP_MISMATCH",
                         f"id={p['id']} expected_phone={p['phone']} got={data.get('phone')}")
            else:
                lu_fail += 1
                _vio("C", "LOOKUP_404",
                     f"id={p['id']} status={resp.status_code if resp else 0}")

    await asyncio.gather(*[lookup_worker(p) for p in sample])

    # ── Duplicate check via full patient list ───────────────────────────────
    async with _client(token) as c:
        resp, _ = await req(c, "GET", "/api/patients", "GET /api/patients")
    all_pts = resp.json() if resp and resp.status_code == 200 else []
    lt_pts  = [p for p in all_pts if LOAD_TAG in (p.get("notes") or "")]

    phone_count: Dict[str, int] = defaultdict(int)
    for p in lt_pts:
        phone_count[p.get("phone", "")] += 1
    dupes = {ph: cnt for ph, cnt in phone_count.items() if cnt > 1}
    if dupes:
        _vio("C", "DUPLICATE_PATIENTS",
             f"phones_with_dupes={json.dumps(dupes)}")

    log.info("scenario_c_done %s", {
        "lookup_ok":        lu_ok,
        "lookup_fail":      lu_fail,
        "lt_patients_in_db": len(lt_pts),
        "duplicate_phones": len(dupes),
        "violations":       len(VIOLATIONS),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO D — Mixed traffic soak
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_d(
    token:      str,
    providers:  List[dict],
    duration_s: int = SOAK_DURATION,
    concurrency: int = CONCURRENCY,
) -> None:
    log.info("scenario_d_start %s", {"duration_s": duration_s, "concurrency": concurrency})

    prov_ids = [p["id"] for p in providers] or SEED_PROVIDERS[:]
    deadline = time.monotonic() + duration_s
    sem      = asyncio.Semaphore(concurrency)

    # Shared pool of cancelable load-test appointment IDs
    live: List[str] = []
    live_lock = asyncio.Lock()

    # Pre-create a reusable soak patient
    patient_id: Optional[str] = None
    async with _client(token) as c:
        resp, _ = await req(
            c, "POST", "/api/patients", "POST /api/patients",
            body={
                "name":  f"{LOAD_TAG} Soak Patient",
                "phone": lt_phone(9999),
                "email": f"soak{LT_EMAIL_SUFFIX}",
                "notes": LOAD_TAG,
            },
        )
        if resp and resp.status_code == 200:
            patient_id = resp.json()["id"]
        elif resp and resp.status_code == 409:
            detail = resp.json().get("detail", {})
            patient_id = (detail.get("patient") or {}).get("id") if isinstance(detail, dict) else None

    if not patient_id:
        log.warning("scenario_d_no_patient %s", {"reason": "cannot create soak patient"})
        return

    # ── Action functions ────────────────────────────────────────────────────

    async def act_list_providers(c: httpx.AsyncClient) -> None:
        await req(c, "GET", "/api/providers", "GET /api/providers")

    async def act_list_appointments(c: httpx.AsyncClient) -> None:
        await req(c, "GET", "/api/appointments", "GET /api/appointments")

    async def act_get_stats(c: httpx.AsyncClient) -> None:
        await req(c, "GET", "/api/stats", "GET /api/stats")

    async def act_practice_config(c: httpx.AsyncClient) -> None:
        await req(
            c, "GET", f"/api/practice/{PRACTICE_ID}/config",
            "GET /api/practice/{id}/config",
        )

    async def act_create_appointment(c: httpx.AsyncClient) -> None:
        prov  = random.choice(prov_ids)
        date  = next_weekday(random.randint(3, 14))
        slot  = rand_slot(9, 16)
        resp, _ = await req(
            c, "POST", "/api/appointments", "POST /api/appointments",
            body={
                "patient_id":       patient_id,
                "patient_name":     f"{LOAD_TAG} Soak Patient",
                "patient_phone":    lt_phone(9999),
                "appointment_date": date,
                "appointment_time": slot,
                "service_type":     random.choice(["cleaning", "exam", "filling", "scaling"]),
                "duration_minutes": 30,
                "provider_id":      prov,
                "notes":            f"{LOAD_TAG} soak",
            },
        )
        if resp and resp.status_code == 200:
            aid = resp.json().get("id")
            if aid:
                async with live_lock:
                    live.append(aid)

    async def act_cancel_appointment(c: httpx.AsyncClient) -> None:
        async with live_lock:
            if not live:
                return
            aid = live.pop(random.randrange(len(live)))
        await req(c, "DELETE", f"/api/appointments/{aid}",
                  "DELETE /api/appointments/{id}")

    # weighted action pool — edit weights here to tune traffic mix
    ACTIONS = [
        (act_list_providers,      3),
        (act_list_appointments,   3),
        (act_get_stats,           2),
        (act_practice_config,     1),
        (act_create_appointment,  4),
        (act_cancel_appointment,  2),
    ]
    pool: List = []
    for fn, w in ACTIONS:
        pool.extend([fn] * w)

    completed = 0
    c_lock    = asyncio.Lock()

    async def worker() -> None:
        nonlocal completed
        while time.monotonic() < deadline:
            fn = random.choice(pool)
            async with sem:
                async with _client(token) as c:
                    await fn(c)
            async with c_lock:
                completed += 1

    tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*tasks)

    log.info("scenario_d_done %s", {
        "requests_completed": completed,
        "duration_s":         duration_s,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Post-run integrity sweep
# ═══════════════════════════════════════════════════════════════════════════════

async def integrity_sweep(
    token:      str,
    providers:  List[dict],
    cfg_before: dict,
) -> None:
    log.info("integrity_sweep_start")

    async with _client(token) as c:
        a_r, _ = await req(c, "GET", "/api/appointments", "GET /api/appointments")
        p_r, _ = await req(c, "GET", "/api/patients",     "GET /api/patients")
        cfg_r, _ = await req(
            c, "GET", f"/api/practice/{PRACTICE_ID}/config",
            "GET /api/practice/{id}/config",
        )

    all_apts  = a_r.json() if a_r  and a_r.status_code  == 200 else []
    all_pts   = p_r.json() if p_r  and p_r.status_code  == 200 else []
    cfg_after = cfg_r.json() if cfg_r and cfg_r.status_code == 200 else {}

    pt_ids   = {p["id"] for p in all_pts}
    prov_ids = {p["id"] for p in providers}

    check_no_double_bookings   ("POST_RUN", all_apts)
    check_valid_statuses       ("POST_RUN", all_apts)
    check_referential_integrity("POST_RUN", all_apts, pt_ids, prov_ids)
    check_settings_immutable   ("POST_RUN", cfg_before, cfg_after)

    log.info("integrity_sweep_done %s", {
        "total_appointments": len(all_apts),
        "total_patients":     len(all_pts),
        "violations":         len(VIOLATIONS),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Cleanup — remove LOAD_TAG-tagged records only
# ═══════════════════════════════════════════════════════════════════════════════

async def cleanup(token: str) -> None:
    log.info("cleanup_start")

    async with _client(token) as c:
        a_r, _ = await req(c, "GET", "/api/appointments", "GET /api/appointments")
        p_r, _ = await req(c, "GET", "/api/patients",     "GET /api/patients")

    all_apts = a_r.json() if a_r and a_r.status_code == 200 else []
    all_pts  = p_r.json() if p_r and p_r.status_code == 200 else []

    lt_apts = [a for a in all_apts if LOAD_TAG in (a.get("notes") or "")]
    lt_pts  = [p for p in all_pts  if LOAD_TAG in (p.get("notes") or "")]

    sem = asyncio.Semaphore(40)

    async def cancel(aid: str) -> None:
        async with sem:
            async with _client(token) as c:
                await req(c, "DELETE", f"/api/appointments/{aid}",
                          "DELETE /api/appointments/{id}")

    async def delete_pt(pid: str) -> None:
        async with sem:
            async with _client(token) as c:
                await req(c, "DELETE", f"/api/patients/{pid}",
                          "DELETE /api/patients/{id}")

    await asyncio.gather(*[cancel(a["id"]) for a in lt_apts])
    await asyncio.gather(*[delete_pt(p["id"]) for p in lt_pts])

    log.info("cleanup_done %s", {
        "appointments_cancelled": len(lt_apts),
        "patients_deleted":       len(lt_pts),
    })


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

async def main(scenarios: List[str], do_cleanup: bool) -> None:
    banner = (
        f"\n{'═'*70}\n"
        f"  Dental AI Stress Test\n"
        f"  base_url    : {BASE_URL}\n"
        f"  scenarios   : {','.join(scenarios)}\n"
        f"  concurrency : {CONCURRENCY}\n"
        f"  soak        : {SOAK_DURATION}s\n"
        f"{'═'*70}\n"
    )
    print(banner)

    token, providers, cfg_before = await bootstrap()

    if "A" in scenarios:
        await scenario_a(LOGIN_WORKERS)

    if "B" in scenarios:
        await scenario_b(token, providers, BOOKING_WORKERS)

    if "C" in scenarios:
        await scenario_c(token, PATIENT_COUNT)

    if "D" in scenarios:
        await scenario_d(token, providers, SOAK_DURATION, CONCURRENCY)

    await integrity_sweep(token, providers, cfg_before)

    if do_cleanup:
        await cleanup(token)

    METRICS.print_summary()

    width = 70
    print("\n" + "═" * width)
    if VIOLATIONS:
        print(f"  ⚠  {len(VIOLATIONS)} INVARIANT VIOLATION(S) DETECTED:")
        for v in VIOLATIONS:
            print(f"     {v}")
    else:
        print("  ✓  All invariants passed — no violations detected.")
    print("═" * width + "\n")

    sys.exit(1 if VIOLATIONS else 0)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dental AI hard stress test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--scenarios",        default="A,B,C,D",
                        help="Comma-separated: A,B,C,D  (default: all)")
    parser.add_argument("--base-url",         default=None,
                        help="Override BASE_URL")
    parser.add_argument("--concurrency",      type=int, default=None,
                        help="Concurrent workers (Scenario D + C lookups)")
    parser.add_argument("--duration",         type=int, default=None,
                        help="Soak duration in seconds (Scenario D)")
    parser.add_argument("--login-workers",    type=int, default=None,
                        help="Login storm workers (Scenario A)")
    parser.add_argument("--booking-workers",  type=int, default=None,
                        help="Booking race workers (Scenario B)")
    parser.add_argument("--patient-count",    type=int, default=None,
                        help="Patients to create (Scenario C)")
    parser.add_argument("--cleanup",          action="store_true",
                        help="Delete all LOAD_TEST-tagged data after the run")
    args = parser.parse_args()

    if args.base_url:      BASE_URL        = args.base_url
    if args.concurrency:   CONCURRENCY     = args.concurrency
    if args.duration:      SOAK_DURATION   = args.duration
    if args.login_workers: LOGIN_WORKERS   = args.login_workers
    if args.booking_workers: BOOKING_WORKERS = args.booking_workers
    if args.patient_count: PATIENT_COUNT   = args.patient_count

    scenarios = [s.strip().upper() for s in args.scenarios.split(",")]
    asyncio.run(main(scenarios, args.cleanup))
