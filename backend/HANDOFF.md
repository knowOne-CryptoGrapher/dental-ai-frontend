# Dental AI — Living Handoff Document
**Last updated:** 2026-08-07
**Backend revision:** dental-ai-backend-00077-97s (unchanged — `update_patient` fix and founding_clinic provisioning fix both committed but not yet deployed, per explicit instruction to hold deploy)
**Frontend commit:** 477a33b0
**Branch:** unlocked-main
**Backend URL:** https://dental-ai-backend-cszmxu7emq-uw.a.run.app
**Frontend URL:** https://frontdeskdentalai.com

---

## Team & Stack
- **Team:** Darnell (builder), Atlas (architect), Claude (co-engineer)
- **Backend:** Python / FastAPI / Cloud Run us-west1
- **Frontend:** React 19 + CRACO / Cloudflare Pages
- **DB:** MongoDB Atlas — database name: `dental_ai` (underscore, not hyphen)
- **Voice:** Retell AI — agent `agent_3420090c2d922714273ae4ad39` provisioned on `practice-test-001` (confirmed live in DB; `phone_number` not yet set in our own `settings.retell`, verify in Retell dashboard whether a number is actually linked before assuming inbound calls route end-to-end)
- **Billing:** Stripe
- **Email:** Amazon SES v2 — production access confirmed, 50,000/day, 14/sec
- **LLM:** Groq default (`llama-3.3-70b-versatile`), Anthropic escalation (`claude-haiku-4-5-20251001`)

---

## Key Credentials & Config
- **Test practice:** `practice-test-001` (plan: professional)
- **Superadmin:** `d9john5@gmail.com`
- **Test admin:** `admin@dentalai.test` / `DentalAI2026!`
- **Test patient phone:** `+12502991248`
- **Retell agent:** `agent_3420090c2d922714273ae4ad39`
- **Sales notify email:** `d.john95@hotmail.com`
- **SES from address:** `noreply@frontdeskdentalai.com`
- **Deploy:** `.\deploy_backend.ps1`
- **Frontend:** auto-deploys on push to `unlocked-main`

---

## Current DB State
*(verified via direct query 2026-08-07, not carried forward from a stale snapshot — counts had drifted from the last-known figures, likely from real usage/testing between sessions)*
- 4 practices (was tracked as 1 — 3 more created since last verified count)
- 4 users
- 2 patients
- 0 appointments
- 2 call logs
- 2 sales leads
- 0 founding clinic applications (feature just shipped this session)

---

## Workflow Rules (Read Every Session)
1. Always specify `C:\Dev\dental-ai-frontend` as project path
2. Always read before fixing — diagnose first, fix in second prompt
3. Never `git add backend/.env` — secrets stay out of git
4. Migration scripts are committed — one-time cleanup scripts are NOT
5. Deploy via `.\deploy_backend.ps1` for backend
6. Frontend auto-deploys on push to `unlocked-main`
7. Token stored as `dental_token` in localStorage
8. Show all diffs before writing — wait for confirmation
9. Never deploy until Darnell confirms diffs
10. Before stress tests — confirm `admin@dentalai.test` exists in DB
11. Before recording facts in this file, verify them against the live system rather than carrying forward a prior draft — several figures in earlier drafts of this doc (DB counts, index counts, revision/commit hashes) were stale by the time they were written down. Treat this file as a snapshot with a timestamp, not a permanent truth.
12. Update this file at the end of every task, not just at the end of a session — standing requirement as of 2026-08-07, don't wait to be asked.

---

## Architecture Notes
- All Retell function calls use `practice_id` from dynamic variables
- `_parse_retell_body` auto-injects `call.from_number` as `patient_phone`
- "Payload: args only" OFF for: `lookup_patient`, `book_appointment`, `get_patient_appointments`, `cancel_appointment`, `register_patient` (unconfirmed by CDA/Retell spec — inferred from the pattern of the other four; verify before relying on it)
- "Payload: args only" ON for all other functions (`list_providers`, `check_provider_availability`, `get_practice_context`, `query_knowledge_base`, `ingest_call_summary`)
- Plan gates return 402 (not 403) for blocked features
- `ENFORCE_PLAN_GATES=true` in Cloud Run via service.yaml
- DB name: `dental_ai` (underscore)
- JWT secret key rotated — version 59 in Secret Manager as of this session's last deploy (verify current version before assuming this is still current; it increments on every deploy since it's provisioned from `.env` each time)
- MongoDB indexes (verified 2026-08-07): 20 indexes across `patients` (5), `appointments` (9, including `booking_key_unique` which prevents double-booking), `providers` (3), `audit_logs` (3). `users` and `practices` currently have only the default `_id_` index.

---

## Active Task — Founding Clinic Modal (DONE this session)
**Status:** Shipped — diffs confirmed, written, deployed, committed, pushed.

### Components built:
1. `frontend/src/components/sales/FoundingClinicModal.jsx` — modal with form, live spots counter, waitlist when full
2. `frontend/src/components/sales/FoundingClinicBanner.jsx` — dismissible top banner
3. `backend/routers/sales_router.py` — 2 new endpoints:
   - `POST /api/sales/founding-clinic`
   - `GET /api/sales/founding-clinic-count`
4. `backend/routers/superadmin_router.py` — 3 new endpoints:
   - `GET /api/superadmin/founding-clinics`
   - `POST /api/superadmin/founding-clinics/{id}/approve`
   - `POST /api/superadmin/founding-clinics/{id}/reject`
5. `frontend/src/pages/PricingPage.jsx` — banner wired at top; Basic plan card gets a live-fetched founding-rate badge + apply button (not hardcoded — pulls real `spots_remaining` from the count endpoint)
6. `frontend/src/pages/LandingPage.jsx` — banner wired at top
7. `frontend/src/pages/SuperAdminDashboardPage.js` — founding clinic applications section with Approve/Reject

### Business rules confirmed:
- 10 spots maximum
- $299/mo locked for life (40% off $499 regular)
- BC clinics only for soft launch
- Rejected emails permanently blocked from reapplying (confirmed intentional, not a bug)
- Live spots counter everywhere it's shown (not hardcoded)
- Submit → "We'll be in touch within 24 hours"

### Known open items (not blockers, just not yet built):
- Founding Clinic modal theme is light (matches the public marketing site), not dark — flagging since it was originally requested as "dark," in case that was intentional for a reason not yet communicated.
- Founding Clinic modal's live marketing copy still says "$499 regular price / 40% off" — actual Basic price in `plans.py` is $399 (~25% off). Pre-existing bug, unrelated to this session's provisioning fix, deliberately left untouched per instruction — see Pending list below.

*(`update_patient` DuplicateKeyError handling — previously listed here — fixed and committed, see Done ✅ below. Not yet deployed.)*

*(A critical gap identified this session — `approve_founding_clinic` only flipped a status flag and never actually created a practice/user/plan, and no `founding_clinic` tier existed in `plans.py` — is now fixed, see Done ✅ below. Not yet deployed.)*

---

## Pre-Launch Checklist

### Done ✅
- Retell voice call flow — agent provisioned (`agent_3420090c2d922714273ae4ad39`), 2 real call logs recorded
- Plan gate verification — 34/34 passing (as previously reported; not re-verified this session)
- Onboarding E2E — all 3 paths verified (as previously reported; not re-verified this session)
- Superadmin lead approval queue
- Patient consent flow
- Legal — Privacy Policy v1.1 + Terms v1.2
- MongoDB indexes — 20 indexes across 4 collections (corrected from a prior "9 indexes" figure — verify count again if this file goes stale)
- Backend hardening — rate limiting, timeouts, JWT scoping (as previously reported; not independently re-verified this session)
- SES v2 — production confirmed 50,000/day, 14/sec
- Load testing — 25 workers, all invariant checks passing
- emergent.sh URLs cleared — full-codebase grep swept this session, 6 files fixed (5 test files + 1 dead router), confirmed no remaining references
- Stripe billing gaps fixed (as previously reported; not independently verified this session)
- Double booking prevention — confirmed via live index check: `appointments.booking_key_unique`
- Admin email notification system — 14 templates, 6/6 tests (as previously reported; not independently verified this session)
- Founding Clinic modal, banner, and admin review queue — built and shipped this session
- `update_patient` DuplicateKeyError handling — same pattern as `create_patient` (commit `0eb42c33`), returns 409 instead of 500 on phone-number collision. Committed as `4e273090`, **not yet deployed** (explicitly held per instruction).
- **Founding Clinic tier + real provisioning** — `founding_clinic` is now a real, distinct entry in `plans.py`'s `PLANS` dict ($299/mo, same feature set as Basic plus a new `insurance_preview: bool` flag on `PlanFeatures` — additive-only, does not touch the real `insurance` gate so Insurance/Claims endpoints stay 402-blocked for these accounts). Marked `public=False` (new `Plan.public` field, defaults `True` for all other tiers) so it's excluded from `GET /billing/plans` and never shows up as a self-serve-subscribable option to existing Basic/Professional/Enterprise/Elite customers. `approve_founding_clinic` (`superadmin_router.py`) now mirrors `approve_lead`'s pattern exactly — creates a real practice (`subscription_plan: "founding_clinic"`), a location, a 72h invite token, sends the welcome email, and writes `practice_id` back onto the application doc — instead of only flipping a status flag as before. Checkout/upgrade to Professional/Enterprise/Elite confirmed to work through the existing generic `/billing/checkout` flow with zero special-casing (validated purely by `plan_id in PLANS`, no hardcoded tier lists). Committed as `2e2fb1a4`, **not yet deployed**.
- **Cloud Run monitoring + alerting** — configured and verified on the `dental-ai-backend` service (us-west1):
  - Notification channel: email to `d9john5@gmail.com` (`projects/dental-ai-backend/notificationChannels/8095552477318138556`). **Created but not yet verified** — GCP sends a confirmation email; until it's clicked, this channel will not deliver alerts.
  - Uptime check on `/health/ready` (verifies Mongo connectivity, not just process liveness — deliberately chosen over `/health/live` since that's the exact failure mode the Atlas payment lapse would have been), every 5 min, 10s timeout (`dental-ai-backend-uptime-4AQ1g7YCSEo`). Config path and live endpoint both independently confirmed correct after a Git-Bash/MSYS path-mangling bug silently broke the first two creation attempts (caught by describing the resource back rather than trusting the create command's success message).
  - Error rate alert policy (`projects/dental-ai-backend/alertPolicies/5969776322765396001`): fires when 5xx ratio exceeds 5% AND total request volume exceeds 20 requests, both over a 5-minute window — volume gate added specifically to avoid false alarms at current low pre-launch traffic. Single MQL condition (GCP disallows mixing MQL conditions with other condition types in one policy). Took several iterations against real API validation errors (field placement, Double/Int type mismatches, rate-vs-delta unit mismatch, integer-division risk) before creating successfully; described back afterward and every field confirmed matching intent.
  - **Not covered:** a second, separate Cloud Run service (`dental-ai-router`, us-central1, `backend/router_service/service.yaml`) has no monitoring configured — out of scope for this task, flagging in case it's wanted later.

### In Progress 🔄
- Incorporation — BC Provincial, lawyer engaged, paperwork in progress

### Pending — No Blockers ⏳
- MongoDB backup configuration
- Refund logic in Stripe
- Data Processing Agreement draft
- Clinic Service Agreement draft
- PHIPA/PIPEDA compliance checklist
- SLA definition document
- Marketing assets (demo video, onboarding PDF, outreach sequences)
- Link a real phone number to the Retell agent in `settings.retell.phone_number` (currently unset in our DB even though the agent itself is provisioned)
- Deploy the `update_patient` DuplicateKeyError fix (committed as `4e273090`, held per explicit instruction — see Done ✅)
- Deploy the founding_clinic tier + real provisioning fix (committed as `2e2fb1a4`, held per explicit instruction — see Done ✅)
- Fix Founding Clinic marketing copy: live copy says "$499 regular price / 40% off," actual Basic price in `plans.py` is $399 (~25% off). Pre-existing bug, found and deliberately left unfixed this session — needs a follow-up prompt.
- Configure `STRIPE_PRICE_FOUNDING_CLINIC` (create a real recurring Stripe Price + set the env var). Without it, `create_checkout_session` silently falls back to a one-time charge instead of a real $299/mo subscription for founding_clinic accounts. Intentionally deferred — test-only software, single user, accepted risk for now.
- Click the verification link sent to `d9john5@gmail.com` for the new monitoring notification channel — alerts are silently inert until this is done
- Fix cosmetic em-dash-to-`?` mangling in the error-rate alert policy's display name (functionality unaffected)
- Minor pre-existing test bug (not introduced this session, confirmed via `git blame` + isolated worktree rerun to predate it by 3+ weeks, commit `608829c37` / 2026-07-13): `tests/test_patient_deduplication.py::test_book_appointment_dedup` fails with `TypeError: object MagicMock can't be used in 'await' expression` — the test's `db.appointments` mock never sets up `find_one` as an `AsyncMock`, but `book_appointment_realtime`'s double-booking conflict check (`retell_api_router.py`) calls `await db.appointments.find_one(...)`. Low priority, but worth a quick fix to keep the suite green.
- More pre-existing, stale plan-tier tests found this session (confirmed via `git show HEAD:backend/plans.py` — the Elite tier and Basic's `audit_log=True` were both already committed in `4f47b31a`, while `test_plan_tiers.py`/`test_billing.py` were last touched in the earlier `4adff4e1` "Initial restore commit" and never updated): `test_plan_registry_has_three_tiers`, `test_basic_plan_disables_escalation_features`, `test_enterprise_unlocks_everything`, and `test_plans_endpoint_public_and_returns_three_plans` all hard-code assumptions from a 3-tier, no-audit-log world. Adding `founding_clinic` this session didn't newly break any of these (each was already failing before this session's diff), but it's worth a follow-up to rewrite them against the current 4-tier (now 5, counting founding_clinic) reality.
- **Sizeable test-coverage gap, not just a pre-existing footnote:** 44 of the 102 tests collected this session (43%) errored at fixture setup because `owner@dentalai.com` and `admin@dentaltest.com` don't exist in the DB this local backend connects to (confirmed via direct read-only Mongo query — `None` for both). That's the entirety of `test_superadmin_re.py` and `test_platform_console.py`, plus most of `test_plan_tiers.py`'s and `test_billing.py`'s HTTP-integration tests — meaning superadmin RBAC, practice suspend/activate, plan-change auditing, and Stripe checkout/portal currently have **zero working local test coverage** until these two accounts are seeded. Unrelated to any code change this session, but it's a real gap, not a shrug-and-move-on item — worth seeding these accounts (or a `conftest.py` fixture that creates them) before relying on this suite to catch regressions.
- Local venv drift discovered this session: `backend/venv/` was missing `slowapi` and `python-json-logger` even though both are pinned in `requirements.txt` (lines 42 and 39) — the venv just predates when those deps were added to the manifest. Reinstalled via `pip install -r requirements.txt` to get the local server running for this session's test pass; not a manifest gap, just worth knowing the checked-in `venv/` can silently drift from `requirements.txt`.

### Pending — Blocked on Incorporation ⏳
- Corporate bank account
- TELUS Health ITRANS registration
- CDA Software Vendor Agreement
- Clinic service agreement signing

### Urgent ⚠️
- None currently. MongoDB Atlas payment (previously flagged here as suspending 07/31/26) is reactivated — independently verified via a live connection check on 2026-08-07 (ping + query against `practices` succeeded, returned 4 documents). If this file goes stale again, re-verify with a direct connection check rather than trusting this line — that's exactly how the previous stale warning happened.

---

## Recent Commits (Last 10)
```
2e2fb1a4 feat(founding-clinic): provision real practice on approval, add founding_clinic plan tier with insurance preview flag
aed40a74 docs: update HANDOFF.md
477a33b0 docs: update HANDOFF.md
4e273090 fix(patients): catch DuplicateKeyError on update_patient, return 409
756a2924 docs: add living HANDOFF.md for session continuity
2de0bbde feat(founding-clinic): soft launch modal, banner, and admin review queue
0eb42c33 fix(patients): add normalized_phone to staff-created patients + catch DuplicateKeyError
33b7654e fix: standardize frontend URL defaults to frontdeskdentalai.com
09dd6cfc fix: replace emergent.sh placeholder URLs with real backend URL
44e318db fix(superadmin): replace emergent.sh placeholder URL with real backend URL
```

---

## How to Update This File
At the end of every Claude Code session, update:
1. Last updated date
2. Backend revision and frontend commit
3. Active task status
4. Pre-launch checklist (move items from In Progress → Done)
5. Recent commits list (`git log --oneline -10` — don't hand-copy from memory, re-run it)
6. **Current DB State — re-query it, don't carry the old numbers forward.** Real usage between sessions changes these counts; this file drifted stale within one session's gap already.

Commit with: `docs: update HANDOFF.md`
