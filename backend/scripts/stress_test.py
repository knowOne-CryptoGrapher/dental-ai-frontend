#!/usr/bin/env python3
"""
Dental AI Backend — Production-Grade Stress Test Harness
=========================================================

Scenarios
---------
  A  Login Storm        — N concurrent logins + protected-endpoint call each
  B  Appointment Race   — N workers race 4 time slots on 1 provider (exposes
                          non-atomic check_provider_conflicts double-booking)
  C  Patient Storm      — N concurrent creates + immediate lookup + dup check
  D  Mixed Soak         — N workers, T seconds, weighted random actions

Post-run
--------
  Integrity Sweep — validates global system correctness via public API
  Cleanup         — removes all [LOAD_TEST]-tagged records (never touches seed)

Usage examples
--------------
  # All scenarios, defaults
  python backend/scripts/stress_test.py

  # Specific scenarios only
  python backend/scripts/stress_test.py --scenarios A,B

  # High-concurrency soak + auto-cleanup + JSON log
  python backend/scripts/stress_test.py --scenarios D --duration 600 \\
      --concurrency 100 --cleanup --log-file soak.jsonl

  # Clean up a previous run without running scenarios
  python backend/scripts/stress_test.py --scenarios "" --cleanup

  # Point at local dev server
  python backend/scripts/stress_test.py --base-url http://localhost:8000

Environment variable overrides (all optional)
----------------------------------------------
  STRESS_BASE_URL        STRESS_ADMIN_EMAIL   STRESS_ADMIN_PASS
  STRESS_PRACTICE_ID     STRESS_CONCURRENCY   STRESS_SOAK_DURATION
  STRESS_LOGIN_WORKERS   STRESS_BOOKING_WORKERS  STRESS_PATIENT_COUNT
  STRESS_TIMEOUT
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION  (env-var overrides listed in module docstring)
# ═══════════════════════════════════════════════════════════════════════════════

BASE_URL       = os.getenv("STRESS_BASE_URL",
                           "https://dental-ai-backend-244697312574.us-west1.run.app")
ADMIN_EMAIL    = os.getenv("STRESS_ADMIN_EMAIL", "admin@dentalai.test")
ADMIN_PASSWORD = os.getenv("STRESS_ADMIN_PASS",  "DentalAI2026!")
PRACTICE_ID    = os.getenv("STRESS_PRACTICE_ID", "practice-test-001")

DEFAULT_LOGIN_WORKERS   = int(os.getenv("STRESS_LOGIN_WORKERS",    "50"))
DEFAULT_BOOKING_WORKERS = int(os.getenv("STRESS_BOOKING_WORKERS", "150"))
DEFAULT_PATIENT_COUNT   = int(os.getenv("STRESS_PATIENT_COUNT",   "300"))
DEFAULT_CONCURRENCY     = int(os.getenv("STRESS_CONCURRENCY",      "50"))
DEFAULT_SOAK_DURATION   = int(os.getenv("STRESS_SOAK_DURATION",   "120"))
REQUEST_TIMEOUT         = float(os.getenv("STRESS_TIMEOUT",        "30.0"))

MAX_RETRIES     = 2       # retries on network/timeout errors only
RETRY_BASE_WAIT = 0.25   # seconds; doubled each retry (exponential backoff)

# ── Test-data tagging ─────────────────────────────────────────────────────────
LOAD_TAG = "[LOAD_TEST]"

# Per-run 3-digit seed embedded in every generated phone number.
# Ensures runs don't collide with each other in the DB.
# E.164 pattern: +1 555 {SEED:03d} {seq:04d} → +1 + 10 digits = valid US.
LT_PHONE_SEED: int = random.randint(100, 999)

# ── Seed data that must never be modified ────────────────────────────────────
SEED_PROVIDERS = [
    "provider-sarah-lee-001",
    "provider-michael-chen-001",
    "provider-emily-rogers-001",
]

SEED_PATIENTS = [
    {"id": "patient-test-001", "name": "James Harlow",   "phone": "+15552000001"},
    {"id": "patient-test-002", "name": "Priya Nair",     "phone": "+15552000002"},
    {"id": "patient-test-003", "name": "Carlos Mendez",  "phone": "+15552000003"},
    {"id": "patient-test-004", "name": "Aisha Thompson", "phone": "+15552000004"},
]

SEED_PATIENT_IDS = {p["id"] for p in SEED_PATIENTS}

# ── Domain constants ──────────────────────────────────────────────────────────
VALID_STATUSES = frozenset({
    "pending_verification", "pending_review",
    "scheduled", "completed", "cancelled", "no_show",
})

SERVICE_TYPES = ["exam", "cleaning", "filling", "consultation", "x-rays", "scaling"]

# Scenario B: race window — 30 days out so it's always a future date
RACE_PROVIDER = "provider-sarah-lee-001"
RACE_SLOTS    = ["09:00", "09:30", "10:00", "10:30"]
RACE_DATE     = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")

# Scenario D: weighted action pool
_SOAK_ACTIONS = [
    ("list_providers",    10),
    ("list_appointments", 20),
    ("get_stats",         10),
    ("get_config",        10),
    ("create_appointment",25),
    ("cancel_appointment",15),
    ("create_patient",    10),
]
_SOAK_NAMES, _SOAK_WEIGHTS = zip(*_SOAK_ACTIONS)

# Realistic name pools for generated patient data
_FIRST = ["Alex","Jordan","Morgan","Taylor","Casey","Riley","Avery","Quinn",
          "Blake","Cameron","Drew","Harper","Logan","Parker","Reese","Sage",
          "Jamie","Charlie","Skyler","Dakota","Robin","Adrian","Devon","Finley"]
_LAST  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
          "Wilson","Anderson","Thomas","Jackson","White","Harris","Martin","Thompson",
          "Lee","Patel","Nguyen","Kim","Okafor","Santos","Rivera","Fernandez"]


# ═══════════════════════════════════════════════════════════════════════════════
# METRICS
# ═══════════════════════════════════════════════════════════════════════════════

class EndpointMetrics:
    """Per-endpoint latency + counters.

    All mutations occur inside the asyncio event loop (single OS thread), so
    no explicit locking is required — Python's GIL makes individual list.append
    and integer += operations atomic at the bytecode level.
    """

    __slots__ = ("latencies", "success", "client_err", "server_err", "net_err")

    def __init__(self) -> None:
        self.latencies:  List[float] = []
        self.success:    int = 0
        self.client_err: int = 0   # 4xx
        self.server_err: int = 0   # 5xx
        self.net_err:    int = 0   # network / timeout after all retries

    def record(self, latency: float, status: int) -> None:
        self.latencies.append(latency)
        if 200 <= status < 300:
            self.success += 1
        elif 400 <= status < 500:
            self.client_err += 1
        elif status >= 500:
            self.server_err += 1
        else:
            self.net_err += 1

    def record_net_err(self, latency: float) -> None:
        self.latencies.append(latency)
        self.net_err += 1

    @property
    def total(self) -> int:
        return self.success + self.client_err + self.server_err + self.net_err

    @property
    def error_rate(self) -> float:
        t = self.total
        return 0.0 if not t else round(
            (self.client_err + self.server_err + self.net_err) / t * 100, 1
        )

    def pct(self, p: float) -> float:
        """Return p-th percentile latency in milliseconds."""
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        idx = max(0, min(math.ceil(len(s) * p / 100) - 1, len(s) - 1))
        return round(s[idx] * 1000, 1)


class Metrics:
    """Global registry: one EndpointMetrics per labelled endpoint + violation log."""

    def __init__(self) -> None:
        self._ep: Dict[str, EndpointMetrics] = defaultdict(EndpointMetrics)
        self.violations: List[str] = []

    def record(self, endpoint: str, latency: float, status: int) -> None:
        self._ep[endpoint].record(latency, status)

    def record_net_err(self, endpoint: str, latency: float) -> None:
        self._ep[endpoint].record_net_err(latency)

    def violation(self, msg: str) -> None:
        self.violations.append(msg)
        print(f"  ✗ INVARIANT VIOLATION: {msg}", flush=True)

    def get(self, endpoint: str) -> EndpointMetrics:
        return self._ep[endpoint]

    def print_summary(self) -> None:
        W = 88
        print("\n" + "═" * W)
        print("  STRESS TEST SUMMARY")
        print("═" * W)

        fmt = "{:<32} {:>7} {:>7} {:>6} {:>6} {:>8} {:>8} {:>8} {:>6}"
        print(fmt.format(
            "ENDPOINT", "TOTAL", "OK", "4xx", "5xx",
            "p50 ms", "p95 ms", "p99 ms", "ERR%",
        ))
        print("─" * W)

        total_req = 0
        for ep in sorted(self._ep):
            m = self._ep[ep]
            if not m.total:
                continue
            total_req += m.total
            print(fmt.format(
                ep[:32],
                m.total,
                m.success,
                m.client_err,
                m.server_err + m.net_err,
                m.pct(50),
                m.pct(95),
                m.pct(99),
                f"{m.error_rate}%",
            ))

        print("─" * W)
        print(f"  Total requests dispatched: {total_req}")

        if self.violations:
            print(f"\n  INVARIANT VIOLATIONS ({len(self.violations)})")
            for v in self.violations:
                print(f"    ✗  {v}")
        else:
            print("\n  All invariant checks PASSED ✓")
        print()


# Module-level singleton — referenced by all scenario functions
METRICS = Metrics()


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

# Set in main() when --log-file is provided
_log_fh: Optional[Any] = None


def _make_client(base_url: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        limits=httpx.Limits(
            max_connections=600,
            max_keepalive_connections=150,
            keepalive_expiry=30,
        ),
        timeout=httpx.Timeout(REQUEST_TIMEOUT),
        follow_redirects=True,
    )


def _auth_header(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def req(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    label: str,
    *,
    token: Optional[str] = None,
    body: Optional[dict] = None,
    params: Optional[dict] = None,
) -> Tuple[int, Optional[Any]]:
    """Execute one HTTP request with exponential-backoff retry on network errors.

    Returns (http_status_code, parsed_json_or_None).
    Every outcome (including errors) is recorded in the global METRICS object.
    """
    headers = _auth_header(token) if token else {}
    retries = 0
    t0 = time.monotonic()

    while True:
        try:
            resp = await client.request(
                method, path,
                headers=headers,
                json=body,
                params=params,
            )
            latency = time.monotonic() - t0
            METRICS.record(label, latency, resp.status_code)

            if _log_fh is not None:
                _log_fh.write(json.dumps({
                    "ts":         datetime.now(timezone.utc).isoformat(),
                    "method":     method,
                    "path":       path,
                    "endpoint":   label,
                    "status":     resp.status_code,
                    "latency_ms": round(latency * 1000, 1),
                }) + "\n")

            try:
                data: Any = resp.json()
            except Exception:
                data = resp.text or None
            return resp.status_code, data

        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            if retries < MAX_RETRIES:
                retries += 1
                await asyncio.sleep(RETRY_BASE_WAIT * (2 ** retries))
                continue
            latency = time.monotonic() - t0
            METRICS.record_net_err(label, latency)
            if _log_fh is not None:
                _log_fh.write(json.dumps({
                    "ts":         datetime.now(timezone.utc).isoformat(),
                    "method":     method,
                    "path":       path,
                    "endpoint":   label,
                    "status":     0,
                    "latency_ms": round(latency * 1000, 1),
                    "error":      str(exc),
                }) + "\n")
            return 0, None


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════

async def _login(
    client: httpx.AsyncClient,
    email: str = ADMIN_EMAIL,
    password: str = ADMIN_PASSWORD,
) -> Optional[str]:
    """Attempt login; return access_token string or None on failure."""
    status, data = await req(
        client, "POST", "/api/auth/login", "auth/login",
        body={"email": email, "password": password},
    )
    if status == 200 and isinstance(data, dict):
        return data.get("access_token")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO A — LOGIN STORM
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_a(client: httpx.AsyncClient, n_workers: int) -> None:
    """N concurrent workers: login → store token → call /auth/me with that token."""
    print(f"\n{'─'*64}", flush=True)
    print(f"[A] LOGIN STORM  workers={n_workers}", flush=True)
    print(f"{'─'*64}", flush=True)

    token_ok   = 0
    token_fail = 0

    async def worker(_: int) -> None:
        nonlocal token_ok, token_fail
        token = await _login(client)
        if not token:
            return
        status, _ = await req(client, "GET", "/api/auth/me", "auth/me", token=token)
        if status == 200:
            token_ok += 1
        else:
            token_fail += 1

    await asyncio.gather(*[worker(i) for i in range(n_workers)])

    m = METRICS.get("auth/login")
    print(f"  logins      total={m.total}  ok={m.success}  "
          f"4xx={m.client_err}  5xx/net={m.server_err + m.net_err}")
    print(f"  token reuse ok={token_ok}  fail={token_fail}")
    print(f"  latency     p50={m.pct(50)} ms  "
          f"p95={m.pct(95)} ms  p99={m.pct(99)} ms")
    print("[A] done", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO B — APPOINTMENT BOOKING RACE
# ═══════════════════════════════════════════════════════════════════════════════

def _appt_payload(patient_idx: int, slot: str, extra_tag: str = "") -> dict:
    p = SEED_PATIENTS[patient_idx % len(SEED_PATIENTS)]
    return {
        "patient_id":       p["id"],
        "patient_name":     p["name"],
        "patient_phone":    p["phone"],
        "appointment_date": RACE_DATE,
        "appointment_time": slot,
        "service_type":     "exam",
        "duration_minutes": 30,
        "provider_id":      RACE_PROVIDER,
        "notes":            f"{LOAD_TAG}[SCENARIO_B]{extra_tag}",
    }


async def scenario_b(
    client: httpx.AsyncClient,
    n_workers: int,
    token: str,
) -> None:
    """N workers race 4 time slots on one provider.

    Designed to expose the non-atomic read-then-write in check_provider_conflicts:
      find_one (no conflict) … find_one (no conflict) … insert … insert  → DOUBLE BOOK
    """
    print(f"\n{'─'*64}", flush=True)
    print(f"[B] APPOINTMENT RACE  workers={n_workers}  "
          f"provider={RACE_PROVIDER}", flush=True)
    print(f"     date={RACE_DATE}  slots={RACE_SLOTS}", flush=True)
    print(f"{'─'*64}", flush=True)

    # Maps appt_id → slot so wave-2 rebooking uses the same slot it freed.
    created: Dict[str, str] = {}
    w1_ok = w1_409 = w1_err = 0

    # ── Wave 1: concurrent booking storm ─────────────────────────────────────
    print("  Wave 1: concurrent create …", flush=True)

    async def book(idx: int) -> None:
        nonlocal w1_ok, w1_409, w1_err
        slot = RACE_SLOTS[idx % len(RACE_SLOTS)]
        status, data = await req(
            client, "POST", "/api/appointments", "appointments/create",
            token=token, body=_appt_payload(idx, slot),
        )
        if status == 200 and isinstance(data, dict) and data.get("id"):
            w1_ok += 1
            created[data["id"]] = slot
        elif status == 409:
            w1_409 += 1
        else:
            w1_err += 1

    await asyncio.gather(*[book(i) for i in range(n_workers)])
    print(f"  Wave 1: ok={w1_ok}  409-conflict={w1_409}  err={w1_err}")

    # ── Wave 2: cancel every created appointment, then rebook same slot ───────
    print("  Wave 2: cancel + rebook …", flush=True)

    w2_cancel = w2_rebook_ok = w2_rebook_409 = 0

    async def cancel_rebook(appt_id: str, idx: int) -> None:
        nonlocal w2_cancel, w2_rebook_ok, w2_rebook_409
        slot = created[appt_id]

        status, _ = await req(
            client, "DELETE", f"/api/appointments/{appt_id}",
            "appointments/cancel", token=token,
        )
        if status != 200:
            return
        w2_cancel += 1

        # Rebook the exact slot we just freed — tests that the slot is now open
        status2, data2 = await req(
            client, "POST", "/api/appointments", "appointments/create",
            token=token, body=_appt_payload(idx, slot, extra_tag="[REBOOK]"),
        )
        if status2 == 200 and isinstance(data2, dict) and data2.get("id"):
            w2_rebook_ok += 1
            created[data2["id"]] = slot   # track rebook ID for cleanup
        elif status2 == 409:
            w2_rebook_409 += 1

    # Freeze the wave-1 snapshot before concurrent appends from rebooks
    snapshot = list(created.items())
    await asyncio.gather(
        *[cancel_rebook(aid, i) for i, (aid, _) in enumerate(snapshot)]
    )
    print(f"  Wave 2: cancelled={w2_cancel}  "
          f"rebook-ok={w2_rebook_ok}  rebook-409={w2_rebook_409}")

    # ── Post-race double-booking assertion ────────────────────────────────────
    print("  Post-race check …", flush=True)

    status, data = await req(
        client, "GET", "/api/appointments", "appointments/list",
        token=token, params={"provider_id": RACE_PROVIDER},
    )
    if status != 200 or not isinstance(data, list):
        METRICS.violation(
            f"[B] Cannot fetch appointments for post-race check (status={status})"
        )
        print("[B] done (post-race check skipped)", flush=True)
        return

    # Active (non-cancelled) load-test appointments on the race date
    active = [
        a for a in data
        if a.get("appointment_date") == RACE_DATE
        and a.get("status") not in ("cancelled", "no_show")
        and LOAD_TAG in (a.get("notes") or "")
    ]

    slot_groups: Dict[str, List[str]] = defaultdict(list)
    for a in active:
        slot_groups[a.get("appointment_time", "?")].append(a.get("id", "?"))

    double_booked = {s: ids for s, ids in slot_groups.items() if len(ids) > 1}
    if double_booked:
        for slot, ids in double_booked.items():
            METRICS.violation(
                f"[B] Double-booking: {RACE_PROVIDER} @ {RACE_DATE} {slot} "
                f"— {len(ids)} active appointments {ids}"
            )
    else:
        print(f"  No double-bookings detected across {len(RACE_SLOTS)} slots ✓")

    # Status validity
    for a in active:
        if a.get("status") not in VALID_STATUSES:
            METRICS.violation(
                f"[B] Invalid status '{a.get('status')}' on id={a.get('id')}"
            )

    print(f"  Active test appointments after race: {len(active)}")
    print("[B] done", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO C — PATIENT CREATION STORM
# ═══════════════════════════════════════════════════════════════════════════════

def _lt_phone(idx: int) -> str:
    """E.164 load-test phone unique to this run + index.
    Pattern: +1 555 {seed:03d} {idx:04d}  →  +1 + 10 digits."""
    return f"+1555{LT_PHONE_SEED:03d}{idx:04d}"


def _lt_email(idx: int) -> str:
    return f"lt{LT_PHONE_SEED:03d}{idx:04d}@stress.test"


async def scenario_c(
    client: httpx.AsyncClient,
    n_patients: int,
    token: str,
) -> None:
    """N concurrent patient creates + sampled lookup verification + dup-rate check."""
    print(f"\n{'─'*64}", flush=True)
    print(f"[C] PATIENT STORM  count={n_patients}  "
          f"phone-seed={LT_PHONE_SEED}", flush=True)
    print(f"{'─'*64}", flush=True)

    created: Dict[int, str] = {}   # idx → patient_id for lookup verification
    c_ok = c_409 = c_err = 0

    async def create_worker(idx: int) -> None:
        nonlocal c_ok, c_409, c_err
        fname = _FIRST[idx % len(_FIRST)]
        lname = _LAST[(idx // len(_FIRST)) % len(_LAST)]
        dob_y = 1950 + (idx % 55)
        dob_m = (idx % 12) + 1
        dob_d = (idx % 28) + 1

        status, data = await req(
            client, "POST", "/api/patients", "patients/create",
            token=token,
            body={
                "name":              f"{fname} {lname}",
                "phone":             _lt_phone(idx),
                "email":             _lt_email(idx),
                "date_of_birth":     f"{dob_y}-{dob_m:02d}-{dob_d:02d}",
                "preferred_contact": "phone",
                "notes":             f"{LOAD_TAG}[SCENARIO_C]",
            },
        )
        if status == 200 and isinstance(data, dict) and data.get("id"):
            c_ok += 1
            created[idx] = data["id"]
        elif status == 409:
            c_409 += 1
        else:
            c_err += 1

    await asyncio.gather(*[create_worker(i) for i in range(n_patients)])
    print(f"  creates: ok={c_ok}  409-dup={c_409}  err={c_err}")

    if not created:
        print("  No patients created — skipping lookup verification")
        print("[C] done", flush=True)
        return

    # ── Sample lookups: verify ~10% of created patients ───────────────────────
    sample_size = max(5, len(created) // 10)
    sample_idxs = random.sample(list(created.keys()), min(sample_size, len(created)))

    lk_ok = lk_fail = lk_mismatch = 0

    async def verify_worker(idx: int) -> None:
        nonlocal lk_ok, lk_fail, lk_mismatch
        pid            = created[idx]
        expected_phone = _lt_phone(idx)

        status, data = await req(
            client, "GET", f"/api/patients/{pid}", "patients/get", token=token,
        )
        if status == 200 and isinstance(data, dict):
            if data.get("phone") == expected_phone:
                lk_ok += 1
            else:
                lk_mismatch += 1
                METRICS.violation(
                    f"[C] Phone mismatch on patient {pid}: "
                    f"got={data.get('phone')}  expected={expected_phone}"
                )
        else:
            lk_fail += 1
            METRICS.violation(
                f"[C] Lookup failed: patient_id={pid} status={status}"
            )

    await asyncio.gather(*[verify_worker(i) for i in sample_idxs])
    print(f"  lookups (sample n={len(sample_idxs)}): "
          f"ok={lk_ok}  fail={lk_fail}  mismatch={lk_mismatch}")

    # ── Duplicate-rate assertion ───────────────────────────────────────────────
    # A small number of 409s is acceptable — leftover patients from a prior run
    # that wasn't cleaned up.  Threshold: 2% of the requested count.
    dup_threshold = max(5, int(n_patients * 0.02))
    if c_409 > dup_threshold:
        METRICS.violation(
            f"[C] Excessive duplicates: {c_409}/{n_patients} 409s exceed "
            f"threshold {dup_threshold} — run --cleanup to remove stale data"
        )
    else:
        print(f"  Duplicate rate {c_409}/{n_patients} within threshold ✓")

    print(f"[C] done  patients_created={len(created)}", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO D — MIXED SOAK TEST
# ═══════════════════════════════════════════════════════════════════════════════

async def scenario_d(
    client: httpx.AsyncClient,
    n_workers: int,
    duration: int,
    token: str,
) -> None:
    """N workers execute weighted-random actions continuously for T seconds."""
    print(f"\n{'─'*64}", flush=True)
    print(f"[D] MIXED SOAK  workers={n_workers}  duration={duration}s", flush=True)
    print(f"{'─'*64}", flush=True)

    stop           = asyncio.Event()
    soak_appt_ids: List[str] = []
    action_count   = 0

    async def worker(worker_id: int) -> None:
        nonlocal action_count
        while not stop.is_set():
            action = random.choices(_SOAK_NAMES, weights=_SOAK_WEIGHTS, k=1)[0]

            if action == "list_providers":
                await req(client, "GET", "/api/providers",
                          "providers/list", token=token)

            elif action == "list_appointments":
                await req(client, "GET", "/api/appointments",
                          "appointments/list", token=token)

            elif action == "get_stats":
                await req(client, "GET", "/api/stats",
                          "stats/get", token=token)

            elif action == "get_config":
                await req(client, "GET", f"/api/practice/{PRACTICE_ID}/config",
                          "practice/config", token=token)

            elif action == "create_appointment":
                p    = random.choice(SEED_PATIENTS)
                slot = random.choice(RACE_SLOTS)
                prov = random.choice(SEED_PROVIDERS)
                status, data = await req(
                    client, "POST", "/api/appointments", "appointments/create",
                    token=token,
                    body={
                        "patient_id":       p["id"],
                        "patient_name":     p["name"],
                        "patient_phone":    p["phone"],
                        "appointment_date": RACE_DATE,
                        "appointment_time": slot,
                        "service_type":     random.choice(SERVICE_TYPES),
                        "duration_minutes": 30,
                        "provider_id":      prov,
                        "notes":            f"{LOAD_TAG}[SCENARIO_D]",
                    },
                )
                if status == 200 and isinstance(data, dict) and data.get("id"):
                    soak_appt_ids.append(data["id"])

            elif action == "cancel_appointment":
                if soak_appt_ids:
                    appt_id = soak_appt_ids.pop(
                        random.randrange(len(soak_appt_ids))
                    )
                    await req(client, "DELETE", f"/api/appointments/{appt_id}",
                              "appointments/cancel", token=token)

            elif action == "create_patient":
                # Use +1444 prefix (differs from Scenario C's +1555) to avoid
                # cross-scenario phone collisions within the same run.
                rnd   = random.randint(0, 9999)
                phone = f"+1444{LT_PHONE_SEED:03d}{rnd:04d}"
                await req(
                    client, "POST", "/api/patients", "patients/create",
                    token=token,
                    body={
                        "name":  f"SoakUser{rnd:04d}",
                        "phone": phone,
                        "notes": f"{LOAD_TAG}[SCENARIO_D]",
                    },
                )

            action_count += 1
            await asyncio.sleep(0)   # yield so stopper coroutine can set the event

    async def stopper() -> None:
        await asyncio.sleep(duration)
        stop.set()

    t0 = time.monotonic()
    await asyncio.gather(*[worker(i) for i in range(n_workers)], stopper())
    elapsed = time.monotonic() - t0

    rps = action_count / elapsed if elapsed > 0 else 0
    print(f"  Total actions: {action_count}  ({rps:.1f} req/s over {elapsed:.1f}s)")
    print("[D] done", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRITY SWEEP
# ═══════════════════════════════════════════════════════════════════════════════

async def integrity_sweep(
    client: httpx.AsyncClient,
    token: str,
    initial_config: dict,
) -> None:
    """Fetch all data via the public API and assert global consistency invariants."""
    print(f"\n{'─'*64}", flush=True)
    print("[SWEEP] Running integrity sweep …", flush=True)
    print(f"{'─'*64}", flush=True)

    _, appointments = await req(client, "GET", "/api/appointments",
                                "sweep/appointments", token=token)
    _, patients     = await req(client, "GET", "/api/patients",
                                "sweep/patients",     token=token)
    _, providers    = await req(client, "GET", "/api/providers",
                                "sweep/providers",    token=token)
    _, curr_config  = await req(client, "GET", f"/api/practice/{PRACTICE_ID}/config",
                                "sweep/config",       token=token)

    appointments = appointments if isinstance(appointments, list) else []
    patients     = patients     if isinstance(patients,     list) else []
    providers    = providers    if isinstance(providers,    list) else []

    patient_ids  = {p["id"] for p in patients}
    provider_ids = {p["id"] for p in providers}

    print(f"  Loaded: {len(appointments)} appointments | "
          f"{len(patients)} patients | {len(providers)} providers")

    v_before = len(METRICS.violations)

    # ── 1. No double-bookings anywhere in the system ──────────────────────────
    slot_map: Dict[Tuple[str, str, str], List[str]] = defaultdict(list)
    for a in appointments:
        if a.get("status") not in ("cancelled", "no_show"):
            pvid = a.get("provider_id") or ""
            dt   = a.get("appointment_date") or ""
            tm   = a.get("appointment_time") or ""
            if pvid and dt and tm:
                slot_map[(pvid, dt, tm)].append(a.get("id", "?"))

    for (pvid, dt, tm), ids in slot_map.items():
        if len(ids) > 1:
            METRICS.violation(
                f"[SWEEP] Double-booking provider={pvid} {dt} {tm} "
                f"— {len(ids)} active: {ids}"
            )

    # ── 2. All appointment statuses are valid ─────────────────────────────────
    for a in appointments:
        s = a.get("status")
        if s not in VALID_STATUSES:
            METRICS.violation(
                f"[SWEEP] Invalid status '{s}' on appointment id={a.get('id')}"
            )

    # ── 3. Referential integrity ──────────────────────────────────────────────
    # The API only returns documents visible to this practice, so unknown IDs
    # genuinely mean broken references.
    for a in appointments:
        pid  = a.get("patient_id")
        pvid = a.get("provider_id")
        if pid and pid not in patient_ids and pid not in SEED_PATIENT_IDS:
            METRICS.violation(
                f"[SWEEP] Appointment {a.get('id')} → unknown patient_id={pid}"
            )
        if pvid and pvid not in provider_ids:
            METRICS.violation(
                f"[SWEEP] Appointment {a.get('id')} → unknown provider_id={pvid}"
            )

    # ── 4. Practice settings immutability ─────────────────────────────────────
    if isinstance(curr_config, dict) and isinstance(initial_config, dict):
        c_s = curr_config.get("settings") or {}
        i_s = initial_config.get("settings") or {}
        for section in ("branding", "emergency"):
            if i_s.get(section) and c_s.get(section) != i_s.get(section):
                METRICS.violation(
                    f"[SWEEP] settings['{section}'] mutated during test run"
                )

    # ── 5. No orphaned active appointments ───────────────────────────────────
    orphaned = [
        a["id"] for a in appointments
        if a.get("patient_id")
        and a["patient_id"] not in patient_ids
        and a["patient_id"] not in SEED_PATIENT_IDS
        and a.get("status") not in ("cancelled", "no_show")
    ]
    if orphaned:
        METRICS.violation(
            f"[SWEEP] {len(orphaned)} orphaned active appointments reference "
            f"missing patients: {orphaned[:5]}{'…' if len(orphaned) > 5 else ''}"
        )

    new_v = len(METRICS.violations) - v_before
    if new_v == 0:
        print("  All integrity checks passed ✓")
    else:
        print(f"  {new_v} violation(s) found — see summary below")

    print("[SWEEP] done", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

async def cleanup(client: httpx.AsyncClient, token: str) -> None:
    """Cancel all LOAD_TAG-tagged appointments and delete LOAD_TAG-tagged patients.

    Seed providers and SEED_PATIENTS are never touched.
    """
    print(f"\n{'─'*64}", flush=True)
    print(f"[CLEANUP] Removing {LOAD_TAG}-tagged records …", flush=True)
    print(f"{'─'*64}", flush=True)

    _, appointments = await req(client, "GET", "/api/appointments",
                                "cleanup/list_appts",    token=token)
    _, patients     = await req(client, "GET", "/api/patients",
                                "cleanup/list_patients", token=token)

    appointments = appointments if isinstance(appointments, list) else []
    patients     = patients     if isinstance(patients,     list) else []

    lt_appts = [
        a for a in appointments
        if LOAD_TAG in (a.get("notes") or "")
    ]
    lt_patients = [
        p for p in patients
        if LOAD_TAG in (p.get("notes") or "")
        and p.get("id") not in SEED_PATIENT_IDS
    ]

    print(f"  Found: {len(lt_appts)} appointments, {len(lt_patients)} patients to remove")

    appts_done    = 0
    patients_done = 0

    # Semaphore to avoid overwhelming the DB with hundreds of parallel deletes
    sem = asyncio.Semaphore(20)

    async def cancel_appt(appt_id: str) -> None:
        nonlocal appts_done
        async with sem:
            status, _ = await req(client, "DELETE", f"/api/appointments/{appt_id}",
                                  "cleanup/cancel_appt", token=token)
            if status == 200:
                appts_done += 1

    async def delete_patient(patient_id: str) -> None:
        nonlocal patients_done
        async with sem:
            status, _ = await req(client, "DELETE", f"/api/patients/{patient_id}",
                                  "cleanup/delete_patient", token=token)
            if status == 200:
                patients_done += 1

    await asyncio.gather(*[cancel_appt(a["id"]) for a in lt_appts])
    await asyncio.gather(*[delete_patient(p["id"]) for p in lt_patients])

    print(f"  Removed: {appts_done}/{len(lt_appts)} appointments  "
          f"{patients_done}/{len(lt_patients)} patients")
    print("[CLEANUP] done", flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# README FOOTER  (printed at end of every run)
# ═══════════════════════════════════════════════════════════════════════════════

_README = """
┌──────────────────────────────────────────────────────────────────────────────┐
│  HOW TO CONFIGURE                                                             │
│                                                                              │
│  CLI flags (override defaults):                                              │
│    --base-url URL          Backend root (default: prod Cloud Run)            │
│    --scenarios A,B,C,D    Subset to run   (default: all four)               │
│    --login-workers N      Concurrent logins for Scenario A  (default: 50)   │
│    --booking-workers N    Concurrent bookers for Scenario B (default: 150)  │
│    --patient-count N      Patients to create in Scenario C (default: 300)   │
│    --concurrency N        Workers for Scenario D soak      (default: 50)    │
│    --duration N           Soak seconds for Scenario D      (default: 120)   │
│    --cleanup              Delete [LOAD_TEST] records after run               │
│    --no-sweep             Skip integrity sweep                               │
│    --log-file PATH        Write JSON-line request log to file                │
│                                                                              │
│  HOW TO CLEAN UP TEST DATA                                                   │
│                                                                              │
│  All test records carry "[LOAD_TEST]" in their notes field.                 │
│  Seed providers and patients (patient-test-00*) are NEVER modified.         │
│                                                                              │
│    Auto-clean after run:                                                     │
│      python backend/scripts/stress_test.py --cleanup                         │
│                                                                              │
│    Clean without re-running:                                                 │
│      python backend/scripts/stress_test.py --scenarios "" --cleanup          │
│                                                                              │
│  HOW TO INTERPRET THE SUMMARY TABLE                                          │
│                                                                              │
│    TOTAL   total HTTP requests sent to that endpoint                         │
│    OK      2xx responses                                                     │
│    4xx     client errors (conflict, not-found, unauthorized)                 │
│    5xx     server errors + network/timeout failures                          │
│    p50 ms  median round-trip latency in milliseconds                         │
│    p95 ms  95th-percentile latency (tail latency)                            │
│    p99 ms  99th-percentile latency (worst-case tail)                         │
│    ERR%    (4xx + 5xx + net-err) / total x 100                               │
│                                                                              │
│  NOTE: 409s on appointments/create during Scenario B are EXPECTED when      │
│  the conflict check fires correctly.  A "[B] Double-booking" violation       │
│  means two workers BOTH passed the check and BOTH inserted — that is the    │
│  real bug in check_provider_conflicts (non-atomic read-then-write).          │
│                                                                              │
│  Exit code: 0 = all invariants passed     1 = one or more violations        │
└──────────────────────────────────────────────────────────────────────────────┘
"""


# ═══════════════════════════════════════════════════════════════════════════════
# CLI + MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Dental AI backend — production-grade stress test harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See module docstring for full usage examples.",
    )
    p.add_argument("--base-url",
                   default=BASE_URL,
                   help="Backend root URL")
    p.add_argument("--scenarios",
                   default="A,B,C,D",
                   help="Comma-separated subset, e.g. A,B  (empty string = none)")
    p.add_argument("--concurrency",
                   type=int, default=DEFAULT_CONCURRENCY,
                   metavar="N")
    p.add_argument("--duration",
                   type=int, default=DEFAULT_SOAK_DURATION,
                   metavar="SECONDS")
    p.add_argument("--login-workers",
                   type=int, default=DEFAULT_LOGIN_WORKERS,
                   metavar="N")
    p.add_argument("--booking-workers",
                   type=int, default=DEFAULT_BOOKING_WORKERS,
                   metavar="N")
    p.add_argument("--patient-count",
                   type=int, default=DEFAULT_PATIENT_COUNT,
                   metavar="N")
    p.add_argument("--cleanup",
                   action="store_true",
                   help="Delete [LOAD_TEST] records after run")
    p.add_argument("--no-sweep",
                   action="store_true",
                   help="Skip the post-run integrity sweep")
    p.add_argument("--log-file",
                   default=None,
                   metavar="PATH",
                   help="Write a JSON-line request log to this path")
    return p


async def _async_main(args: argparse.Namespace) -> int:
    global _log_fh

    scenarios = {s.strip().upper() for s in args.scenarios.split(",") if s.strip()}

    if args.log_file:
        _log_fh = open(args.log_file, "w", encoding="utf-8")  # noqa: WPS515

    W = 64
    print("═" * W)
    print("  DENTAL AI STRESS TEST HARNESS")
    print(f"  Target    : {args.base_url}")
    print(f"  Scenarios : {', '.join(sorted(scenarios)) or '(none — cleanup only)'}")
    print(f"  Race date : {RACE_DATE}  phone-seed={LT_PHONE_SEED}")
    print(f"  Started   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * W)

    async with _make_client(args.base_url.rstrip("/")) as client:

        # ── Bootstrap: obtain admin token ─────────────────────────────────────
        print("\n[INIT] Authenticating …", flush=True)
        token = await _login(client)
        if not token:
            print(
                "FATAL: login failed — check credentials and --base-url",
                file=sys.stderr,
            )
            return 1
        print("[INIT] Token obtained ✓", flush=True)

        # Capture config before any mutations for the settings-immutability check
        initial_config: dict = {}
        if not args.no_sweep:
            _, initial_config = await req(
                client, "GET", f"/api/practice/{PRACTICE_ID}/config",
                "init/config", token=token,
            )
            if not isinstance(initial_config, dict):
                initial_config = {}

        t0 = time.monotonic()

        # ── Scenarios ─────────────────────────────────────────────────────────
        if "A" in scenarios:
            await scenario_a(client, args.login_workers)

        if "B" in scenarios:
            await scenario_b(client, args.booking_workers, token)

        if "C" in scenarios:
            await scenario_c(client, args.patient_count, token)

        if "D" in scenarios:
            await scenario_d(client, args.concurrency, args.duration, token)

        elapsed = time.monotonic() - t0
        if scenarios:
            print(f"\n[RUN] Scenarios complete in {elapsed:.1f}s")

        # ── Post-run integrity sweep ───────────────────────────────────────────
        if not args.no_sweep:
            await integrity_sweep(client, token, initial_config)

        # ── Cleanup ───────────────────────────────────────────────────────────
        if args.cleanup:
            await cleanup(client, token)

    # ── Final output ──────────────────────────────────────────────────────────
    METRICS.print_summary()

    if _log_fh is not None:
        _log_fh.close()
        print(f"  JSON request log: {args.log_file}")

    print(_README)

    return 1 if METRICS.violations else 0


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_async_main(args)))


if __name__ == "__main__":
    main()
