# Dental AI — Living Handoff Document
**Last updated:** 2026-08-07
**Backend revision:** dental-ai-backend-00077-97s
**Frontend commit:** 2de0bbde
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
- No exception handling around `update_patient`'s write to `normalized_phone` — could throw an uncaught `DuplicateKeyError` → 500 if a phone update collides with another patient's number in the same practice. Same class of bug fixed on `create_patient` this session; `update_patient` wasn't in scope.
- Founding Clinic modal theme is light (matches the public marketing site), not dark — flagging since it was originally requested as "dark," in case that was intentional for a reason not yet communicated.

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

### In Progress 🔄
- Incorporation — BC Provincial, lawyer engaged, paperwork in progress

### Pending — No Blockers ⏳
- MongoDB backup configuration
- Monitoring + alerting setup (Cloud Run metrics, error rate alerts)
- Refund logic in Stripe
- Data Processing Agreement draft
- Clinic Service Agreement draft
- PHIPA/PIPEDA compliance checklist
- SLA definition document
- Marketing assets (demo video, onboarding PDF, outreach sequences)
- Link a real phone number to the Retell agent in `settings.retell.phone_number` (currently unset in our DB even though the agent itself is provisioned)
- `update_patient` DuplicateKeyError handling (see Known open items above)

### Pending — Blocked on Incorporation ⏳
- Corporate bank account
- TELUS Health ITRANS registration
- CDA Software Vendor Agreement
- Clinic service agreement signing

### Urgent ⚠️
- MongoDB Atlas payment — suspends 07/31/26 (**check this date — if "Last updated" above is later than 07/31/26, this may already have happened or needs updating**)

---

## Recent Commits (Last 10)
```
2de0bbde feat(founding-clinic): soft launch modal, banner, and admin review queue
0eb42c33 fix(patients): add normalized_phone to staff-created patients + catch DuplicateKeyError
33b7654e fix: standardize frontend URL defaults to frontdeskdentalai.com
09dd6cfc fix: replace emergent.sh placeholder URLs with real backend URL
44e318db fix(superadmin): replace emergent.sh placeholder URL with real backend URL
4012d32a fix(superadmin-retell): replace automation badge with manual setup flow
dedf43c4 fix(patients): add consent endpoint and Mark Consent button
1cbd0ed7 fix(plans+onboarding): gate Enterprise/Elite behind contact sales
a30d4d9b feat(superadmin): lead approval queue + country/province fields
3bb37c66 feat(onboarding): hardening batch + email + security fixes
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
