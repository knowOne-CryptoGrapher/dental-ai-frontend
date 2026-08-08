# Dental AI — Living Handoff Document
**Last updated:** 2026-08-08
**Backend revision:** dental-ai-backend-00079-9rx (deployed 2026-08-08 — Retell function-call signature-verification fix, promoted to 100% traffic after isolated live verification, see Urgent section below)
**Frontend commit:** b6cf1b0c (pushed and auto-deployed to Cloudflare Pages)
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
13. Report in full detail, not summarized — show exact code/config found (not paraphrased), exact commands run and their raw output, exact error messages, and reasoning for any judgment calls made along the way, not just conclusions. If something is uncertain or was inferred rather than directly confirmed, say so explicitly rather than stating it as fact. Flag anything unexpected immediately rather than folding it silently into a later summary. Standing requirement as of 2026-08-07.

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
- `update_patient` DuplicateKeyError handling — same pattern as `create_patient` (commit `0eb42c33`), returns 409 instead of 500 on phone-number collision. Committed as `4e273090`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`**.
- **Founding Clinic tier + real provisioning** — `founding_clinic` is now a real, distinct entry in `plans.py`'s `PLANS` dict ($299/mo, same feature set as Basic plus a new `insurance_preview: bool` flag on `PlanFeatures` — additive-only, does not touch the real `insurance` gate so Insurance/Claims endpoints stay 402-blocked for these accounts). Marked `public=False` (new `Plan.public` field, defaults `True` for all other tiers) so it's excluded from `GET /billing/plans` and never shows up as a self-serve-subscribable option to existing Basic/Professional/Enterprise/Elite customers. `approve_founding_clinic` (`superadmin_router.py`) now mirrors `approve_lead`'s pattern exactly — creates a real practice (`subscription_plan: "founding_clinic"`), a location, a 72h invite token, sends the welcome email, and writes `practice_id` back onto the application doc — instead of only flipping a status flag as before. Checkout/upgrade to Professional/Enterprise/Elite confirmed to work through the existing generic `/billing/checkout` flow with zero special-casing (validated purely by `plan_id in PLANS`, no hardcoded tier lists). Committed as `2e2fb1a4`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`**.
- **Cloud Run monitoring + alerting** — configured and verified on the `dental-ai-backend` service (us-west1):
  - Notification channel: email to `d9john5@gmail.com` (`projects/dental-ai-backend/notificationChannels/8095552477318138556`). **Created but not yet verified** — GCP sends a confirmation email; until it's clicked, this channel will not deliver alerts.
  - Uptime check on `/health/ready` (verifies Mongo connectivity, not just process liveness — deliberately chosen over `/health/live` since that's the exact failure mode the Atlas payment lapse would have been), every 5 min, 10s timeout (`dental-ai-backend-uptime-4AQ1g7YCSEo`). Config path and live endpoint both independently confirmed correct after a Git-Bash/MSYS path-mangling bug silently broke the first two creation attempts (caught by describing the resource back rather than trusting the create command's success message).
  - Error rate alert policy (`projects/dental-ai-backend/alertPolicies/5969776322765396001`): fires when 5xx ratio exceeds 5% AND total request volume exceeds 20 requests, both over a 5-minute window — volume gate added specifically to avoid false alarms at current low pre-launch traffic. Single MQL condition (GCP disallows mixing MQL conditions with other condition types in one policy). Took several iterations against real API validation errors (field placement, Double/Int type mismatches, rate-vs-delta unit mismatch, integer-division risk) before creating successfully; described back afterward and every field confirmed matching intent.
  - **Not covered:** a second, separate Cloud Run service (`dental-ai-router`, us-central1, `backend/router_service/service.yaml`) has no monitoring configured — out of scope for this task, flagging in case it's wanted later.
- **Seeded the missing test-fixture accounts** — `owner@dentalai.com` (`OwnerPass123!`, `super_admin`) and `admin@dentaltest.com` (`TestPass123!`, `admin`, linked to a new dedicated practice `practice-fixture-admin-001`) didn't exist in the DB, which was the root cause of 44/102 test errors reported last session. Seeded via `backend/scripts/seed_test_fixtures.py` (idempotent, written to match the existing committed-migration-script convention — matches the shape of the older `create_admin.py`/`init_db.py` in that directory, but reads `MONGODB_URI`/`DATABASE_NAME` from `.env` rather than hardcoding credentials; not yet committed as of this HANDOFF update — see next steps). Shape derived directly from how the 10 test files that reference these accounts use them (login fields, roles, practice linkage), not guessed.
  - Confirmed fix, same 7-file/102-test scope as last session's baseline: **54 passed / 4 failed / 44 errors → 74 passed / 5 failed / 23 errors.** Zero `"Invalid email or password"` failures anywhere (verified directly), including across the full ~470-test suite — the login gap is fully closed.
  - The 5th "failure" (`test_superadmin_plans_endpoint`) isn't a new regression — it's the same already-documented stale "3-tier world" assumption (see above), just newly visible now that its `super_token` fixture can actually log in instead of erroring out first.
  - Of the remaining 23 errors: 0 are login-related. 4 are rate-limiter self-collision from running many login-dependent modules back-to-back in one local `pytest` invocation (see Pending below — not a defect). The other 19 are two distinct, unrelated, pre-existing gaps that were simply hidden behind the login failure until now (also detailed in Pending below): `test_superadmin_re.py`'s onboarding-router-disabled 404 (12 tests), and `test_platform_console.py`'s missing-`province`-field 422 (7 tests).
- **Founding Clinic simplified back to a single tier** — a Professional founding-clinic variant (`founding_clinic_professional`, $399/mo) was fully scoped and diff-reviewed this session but never written to disk (confirmed via `git status` before starting the revert — all 8 files were still untouched). It's cancelled, not deferred. The plan originally shipped as `founding_clinic` (commit `2e2fb1a4`, see above) is renamed to `founding_clinic_basic` — same $299/mo price, same features, same everything, just the id. `approve_founding_clinic` now hardcodes `subscription_plan: "founding_clinic_basic"` directly — no tier branching, since there's only one tier again. Two frontend improvements survive the cancellation: crossed-out regular-vs-founding pricing display on both `PricingPage.jsx` and `LandingPage.jsx` (the latter had zero founding-clinic wiring before this — built fresh), and the founding pricing/CTA now disappears entirely once combined spots hit 0 (previously fell back to a "waitlist open" state that stayed visible/clickable forever) — `FoundingClinicBanner.jsx` also auto-hides at 0 spots now, alongside its existing manual dismiss. Committed as `fb96cd03`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`**.
  - Reran the same 7-file/102-test scope: 74 passed / 5 failed / 23 errors → **71 passed / 8 failed / 23 errors**. The 3 new failures are **not** caused by this change — confirmed via a direct Stripe API query that the `basic plan` and `professional plan` Stripe Products are currently `product.active=False` (enterprise/elite remain active), so `/billing/checkout` 502s for those two plans regardless of any code here. See Urgent below. The other 5 failures and all 23 errors are the exact same pre-existing issues already documented above (stale 3-tier-world test assumptions, onboarding-router-disabled 404s, missing-`province`-field 422s, rate-limiter self-collision).
- **Self-serve signup locked to Basic only — Task B1, backend gate (B2 frontend UI still pending, see Pending below)** — new `SELF_SERVE_TIERS_ENABLED: set[str] = {"basic"}` in `plans.py` (right after `DEFAULT_PLAN_ID`) is now the single source of truth for which plans can be self-serve-registered, independent of `PLANS` (structural validity) and `Plan.public` (billing-page upgrade visibility). Wired into **both** self-serve paths: `practice_router.py`'s `POST /practices` (the old `_VALID_PLANS = {"basic","professional","enterprise","elite"}` set was removed entirely — confirmed it had no other consumer in the codebase — and replaced with a `SELF_SERVE_TIERS_ENABLED` membership check); and `auth_router.py`'s `POST /auth/register`, which previously hardcoded `subscription_plan: "basic"` completely unconditionally with **no plan concept and no gate at all** — now defensively checks `"basic" in SELF_SERVE_TIERS_ENABLED` first, so it won't silently keep granting free practices if `basic` itself gets locked later (e.g. a full signup freeze). Superadmin manual plan assignment, founding-clinic provisioning, and billing-page upgrades all bypass this gate entirely — unaffected by design.
  - **Closes a real, live gap, not just defense-in-depth**: found during discovery that `OnboardingWizard.js` reads its plan selection straight from a URL query param (`?plan=professional`) with zero live-availability check before submitting — anyone navigating there directly (no click-path needed, no dev-flag gating, works in any environment) could previously self-serve into Professional/Enterprise/Elite for free. Now blocked server-side with `400 {"detail": "Self-serve signup is currently limited to: basic. Contact sales for other plans."}`.
  - Committed as `a4f7589a`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`**.
  - Tests confirmed via clean isolated reruns (server restarted between runs to avoid rate-limiter cross-contamination): this **intentionally** breaks `test_plan_gates_professional.py` (9 tests) and `test_registration_flow_enterprise.py` (9 tests) — both self-serve-register a locked plan and were previously passing because that was allowed; they now correctly error on the new 400 (verified the exact message, nothing else). Not a regression — these 2 files need rewriting in a follow-up to assert the block instead of asserting success (not done this session). Everything else in the established 7-file baseline is unchanged from the prior known state (same 8 pre-existing failures, same 23 pre-existing errors). Also spot-checked `test_multi_tenant_isolation.py` in isolation (17/17 passed) confirming `/auth/register`'s `basic` path is completely unaffected.
- **Task B2 complete — "Coming Soon" UI for the locked Professional tier (Task B = B1 + B2 is now done in full).** `plans.py`'s `Plan.public_dict()` gained `self_serve_enabled: bool` (`self.id in SELF_SERVE_TIERS_ENABLED`), riding on the already-public `GET /billing/plans` — zero new backend endpoint, and the frontend reads this live rather than hardcoding yet another duplicate tier-availability list (exactly the scattered-arrays problem flagged repeatedly in earlier discovery). `PricingPage.jsx`, `LandingPage.jsx` (via `PricingPreviewCard.jsx`), and `OnboardingWizard.js` (including its own Step 2 plan-picker grid, not just the marketing pages) all fetch this once on mount and show a "Coming Soon" badge plus a genuinely non-interactive replacement for the CTA (a plain `<span>`, no `href`/`onClick` at all — not just a styled-disabled real link) — defaulting to locked until the fetch confirms otherwise, so there's no flash/flicker.
  - **Scoped to Professional only** — Enterprise/Elite keep their existing, fully unchanged Contact Sales path everywhere (a separate, permanent, human-mediated flow, not part of the self-serve gate). An initial draft accidentally locked all three; caught and corrected mid-review before anything was written. Basic's card/flow is untouched everywhere, not even wrapped in a loading-state check.
  - `OnboardingWizard.js` also gets a general early-redirect safety net (deliberately **not** Professional-scoped, unlike the visual lock) — if `selectedPlan` resolves to *any* plan not in `SELF_SERVE_TIERS_ENABLED` (covers a direct `?plan=enterprise`/`?plan=elite` URL too, not just professional), it toasts an explanation and redirects to `/pricing` immediately instead of letting the whole 11-step form get filled out before hitting the raw 400 at the very end.
  - Committed as `b0a7d23a`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`**. Tests: reran the established 6-file baseline (excluding `test_plan_gates_professional.py`, already known broken from B1 — see above): 60 passed / 8 failed / 23 errors, identical failure/error set to the already-diagnosed pre-existing baseline — zero regressions from the new field or any UI change. Directly verified `GET /billing/plans` returns `basic: true, professional: false, enterprise: false, elite: false`.
- **Full pricing correction sweep — Basic → $499 CAD, Professional → $699 CAD.** Enterprise ($999) and Elite ($1,499) untouched throughout, confirmed via repo-wide grep. `plans.py`'s `price_usd` updated for both tiers. All 5 previously-flagged hardcoded frontend copies corrected: `PricingPage.jsx` (both its `PLANS` **and** `PLAN_COLS` arrays — two independent copies in one file), `LandingPage.jsx`, `ComparePlansModal.js`, `OnboardingWizard.js`'s `WIZARD_PLANS`. `BillingPage.js` confirmed to need no changes — its only hardcoded literal is the untouched Elite `$1,499` upsell CTA. `founding_clinic_basic`'s `$299` confirmed still fully independent, untouched.
  - New Stripe Price objects configured in `.env`: `STRIPE_PRICE_BASIC` and `STRIPE_PRICE_PROFESSIONAL` now point at real, active, CAD Price objects — verified live via direct Stripe API query ($499.00 CAD / $699.00 CAD, both `active=True`, matching Enterprise/Elite's existing setup). **Caught before writing**: the IDs initially supplied were Stripe *Product* IDs (`prod_...`), not *Price* IDs (`price_...`) — using them as-is would have broken checkout outright (`InvalidRequestError: No such price`). Resolved each Product's `default_price` to the actual Price ID first. `.env` not committed, per standing rule.
  - Two more Stripe Product IDs were supplied alongside these but **not** wired into anything (outside this task's approved scope): a Founding-Clinic-Basic product ($299 CAD — matches `founding_clinic_basic` exactly, could satisfy the still-open `STRIPE_PRICE_FOUNDING_CLINIC` gap below if picked up later) and a Founding-Clinic-Professional product ($399 CAD) — the latter corresponds to the `founding_clinic_professional` tier that was explicitly **cancelled** earlier this session (Task A). Flagging that Stripe-side infrastructure for the cancelled tier exists even though no `plans.py` entry does, in case it's worth cleaning up on the Stripe side later.
  - **Resolves the 3 Stripe-checkout test failures flagged as Urgent last update** (see Urgent, now cleared) — confirmed directly, not assumed: `test_checkout_creates_stripe_session`, `test_checkout_persists_pending_transaction`, `test_reconcile_idempotent_on_already_promoted` all now **PASS**. Also updated `test_billing.py::test_basic_plan_pricing_matches_business_decision` (previously asserted the old `399.0`/`599.0` values, would otherwise have newly broken) to assert the corrected prices — confirmed passing.
  - `FoundingClinicModal.jsx` needed no changes — its "$499 regular price / 40% off" copy is now accurate as a side effect: $499 − $299 = $200 off, $200/$499 = 40.08% ≈ 40%. Previously-tracked pre-existing bug, now resolved.
  - Tests, same 6-file scope as B1/B2's baseline: 60 passed / 8 failed / 23 errors → **63 passed / 5 failed / 23 errors**. The 3 resolved Stripe-checkout failures account for the full delta; the remaining 5 failures and all 23 errors are the exact same pre-existing, already-diagnosed issues (stale 3-tier-world test assumptions, onboarding-router-disabled 404s, missing-`province`-field 422s, rate-limiter self-collision) — unrelated to pricing, unchanged.
  - Committed as `860ff136`, **deployed 2026-08-07 in revision `dental-ai-backend-00078-9j6`** — confirmed live via direct `GET /billing/plans` query against production (see deploy-confirmation entry below).
- **DEPLOY POINT — all of today's batched work pushed and live in production, 2026-08-07.** Pushed 15 commits (`756a2924..b6cf1b0c`) to `origin/unlocked-main`. Backend deployed via `.\deploy_backend.ps1` → revision `dental-ai-backend-00078-9j6` (all Secret Manager values reprovisioned from `.env`, including the corrected `STRIPE_PRICE_BASIC`/`STRIPE_PRICE_PROFESSIONAL`). Frontend auto-deployed to Cloudflare Pages on push (commit `b6cf1b0c`) — Wrangler CLI couldn't verify build status directly on this machine (Node v18 installed, Wrangler needs v20+), so confirmed indirectly instead: the live bundle at `frontdeskdentalai.com/pricing` contains `"$499"` and no longer contains `"$399"`.
  - **Post-deploy smoke check against live production (not just local tests):** `GET /health/ready` → `200 {"status":"ready","db":"ok",...}`. `GET /api/billing/plans` → `200`, confirmed `basic: 499.0/self_serve_enabled=true`, `professional: 699.0/self_serve_enabled=false`, `enterprise: 999.0/self_serve_enabled=false`, `elite: 1499.0/self_serve_enabled=false` — matches expectations exactly.
  - Deploy script note: the first invocation attempt failed with a misleading `NativeCommandError` after only updating one secret — caused by wrapping the script call in `2>&1 | Tee-Object`, which is the known PowerShell 5.1 anti-pattern of redirecting a native command's stderr (gcloud writes normal success messages to stderr). Re-ran without the wrapper and it completed cleanly end-to-end. No lasting effect — the one secret version created before the false failure (`MONGODB_URI`) had an unchanged value, harmless.
  - Everything previously logged as "not yet deployed" above (patient dedup fix, founding_clinic provisioning + rename, self-serve signup lockdown, Task B2 Coming Soon UI, pricing correction) is now live in this same revision — updated each entry above accordingly rather than leaving stale markers.

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
- Rewrite `test_plan_gates_professional.py` and `test_registration_flow_enterprise.py` to assert the new self-serve-blocked 400 instead of asserting a successful self-serve professional/enterprise signup — both now correctly error as a direct, intended result of the B1 lockdown above, not a bug, but the tests themselves are stale against the new business rule.
- **26 tests need updating to send a real `X-Retell-Signature`** now that `retell_api_router.py`'s auth fix is live in production (see Urgent above — FIXED, DEPLOYED, LIVE-VERIFIED as of 2026-08-08): `test_multi_tenant_isolation.py` (5 tests) and `test_retell_hard_suite.py` (21 tests) currently call these endpoints with no signature at all and now correctly get `401`. Pattern to use: `retell.lib.webhook_auth.symmetric["sign"](body_str, RETELL_API_KEY)`, confirmed working during this fix's local verification.
- Configure `STRIPE_PRICE_FOUNDING_CLINIC` (the env var `founding_clinic_basic` actually reads — set the real recurring Stripe Price ID). A Stripe Product matching this exactly (`$299 CAD`) was created and supplied this session but deliberately not wired in (outside this task's approved scope — see the pricing-sweep entry above for the Product/Price ID note). Without it, `create_checkout_session` silently falls back to a one-time charge instead of a real $299/mo subscription for founding_clinic_basic accounts. Intentionally deferred — test-only software, single user, accepted risk for now.
- Click the verification link sent to `d9john5@gmail.com` for the new monitoring notification channel — alerts are silently inert until this is done
- Fix cosmetic em-dash-to-`?` mangling in the error-rate alert policy's display name (functionality unaffected)
- Minor pre-existing test bug (not introduced this session, confirmed via `git blame` + isolated worktree rerun to predate it by 3+ weeks, commit `608829c37` / 2026-07-13): `tests/test_patient_deduplication.py::test_book_appointment_dedup` fails with `TypeError: object MagicMock can't be used in 'await' expression` — the test's `db.appointments` mock never sets up `find_one` as an `AsyncMock`, but `book_appointment_realtime`'s double-booking conflict check (`retell_api_router.py`) calls `await db.appointments.find_one(...)`. Low priority, but worth a quick fix to keep the suite green.
- More pre-existing, stale plan-tier tests found this session (confirmed via `git show HEAD:backend/plans.py` — the Elite tier and Basic's `audit_log=True` were both already committed in `4f47b31a`, while `test_plan_tiers.py`/`test_billing.py` were last touched in the earlier `4adff4e1` "Initial restore commit" and never updated): `test_plan_registry_has_three_tiers`, `test_basic_plan_disables_escalation_features`, `test_enterprise_unlocks_everything`, and `test_plans_endpoint_public_and_returns_three_plans` all hard-code assumptions from a 3-tier, no-audit-log world. Adding `founding_clinic` this session didn't newly break any of these (each was already failing before this session's diff), but it's worth a follow-up to rewrite them against the current 4-tier (now 5, counting founding_clinic) reality.
- Local venv drift discovered this session: `backend/venv/` was missing `slowapi` and `python-json-logger` even though both are pinned in `requirements.txt` (lines 42 and 39) — the venv just predates when those deps were added to the manifest. Reinstalled via `pip install -r requirements.txt` to get the local server running for this session's test pass; not a manifest gap, just worth knowing the checked-in `venv/` can silently drift from `requirements.txt`.
- Two more pre-existing, unrelated gaps surfaced now that the fixture-account login blocker (below, see Done ✅) is fixed — these were previously hidden behind the 44 login errors and never ran far enough to be seen:
  - `test_superadmin_re.py`'s own `practice_admin` fixture calls `POST /api/onboarding/practice`, which 404s because `onboarding_router` is commented out in `server.py` (`# app.include_router(onboarding_router)`). Every test in that file transitively depends on it, so all 12 error. Unknown whether the router is disabled intentionally or by accident — worth a quick look.
  - `test_platform_console.py`'s `created_practice` fixture posts to `POST /superadmin/practices` without a `province` field, which that endpoint now requires (422 `Field required`). 7 tests in that file depend on it and error as a result. Test/schema drift, same category as the stale plan-tier tests above.
  - Local test runs are also naturally rate-limited: `/auth/login` allows 5 requests per 15 minutes per IP (not per-account), and this test battery needs ~6 logins across its module-scoped fixtures when run in one `pytest` invocation from a single machine — expect a handful of `429 Too Many Requests` on any full run rather than treating them as regressions. Restarting the local server resets the in-memory limiter if a clean read is needed.

### Pre-Launch Test Data To Wipe ⏳ (not urgent — same shared DB as prod today, see note above; clear alongside everything else at soft launch)
- `owner@dentalai.com` / super_admin login, no practice (seeded this session — `backend/scripts/seed_test_fixtures.py`)
- `admin@dentaltest.com` / practice admin (seeded this session — same script)
- `practice-fixture-admin-001` — the practice created for `admin@dentaltest.com` (seeded this session — same script)
- `practice-test-001` / `admin@dentalai.test` — earlier test practice + admin (see Key Credentials & Config above, predates this session)

### Pending — Blocked on Incorporation ⏳
- Corporate bank account
- TELUS Health ITRANS registration
- CDA Software Vendor Agreement
- Clinic service agreement signing

### Urgent ⚠️
- **Full production security/leakage/load audit run 2026-08-07 against the live deploy — 2 critical findings + 1 moderate. Finding #1 is FIXED, DEPLOYED, and LIVE-VERIFIED as of 2026-08-08. Finding #2 and the moderate finding are still OPEN.** Full findings reported in-conversation, not duplicated in full here:
  1. **`retell_api_router.py`'s 7 patient/appointment/provider endpoints (lookup-patient, book-appointment, cancel-appointment, register-patient, etc.) had no real authentication in production** — they read an `x_retell_signature` header and API key but discarded both (`_ = (retell_api_key, x_retell_signature, body_bytes)`); a working `verify_retell_signature()` HMAC function existed in the same file but was never called. Confirmed live (2026-08-07, pre-fix): `list-providers` and `lookup-patient` both returned real `200` data for a guessed `practice_id` with zero credentials.
     - **STATUS: FIXED, DEPLOYED, AND LIVE-VERIFIED (2026-08-08).**
     - Root cause and fix: the local `verify_retell_signature()` used the wrong header format (`t=`,`v1=` — the Stripe convention) and would never have matched a real Retell signature (`v=`,`d=`) even if called. Removed it. Reused `utils/retell_security.py`'s `verify_retell_webhook_signature()` — already correct, already used by `/api/retell/webhook` — called with `RETELL_API_KEY` instead of the webhook secret, via a new shared `_verify_retell_call()` helper called first in all 7 endpoints. Committed as `cf5173cf` (`fix(retell): enforce signature verification on all 7 custom-function endpoints`), pushed to `origin/unlocked-main`.
     - Local test (both directions) confirmed before deploy: no signature → `401`; stale/garbage/tampered/fabricated signatures → `401`; a real signature generated via the actual `retell` SDK's own `sign()` function → `200` with real data.
     - **Live verification methodology (2026-08-08), fully isolated from production traffic and the real phone number until the result was confirmed:**
       1. Deployed the fix as a new Cloud Run revision (`dental-ai-backend-00079-9rx`) via `gcloud run deploy --image=<digest-pinned> --no-traffic --region us-west1 --project dental-ai-backend` — confirmed via `gcloud run services describe` that production stayed 100% on the old revision (`dental-ai-backend-00078-9j6`) throughout.
       2. Assigned a traffic tag (`gcloud run services update-traffic --update-tags=retell-fix-test=dental-ai-backend-00079-9rx`) to get a stable direct URL for the isolated revision without shifting any traffic: `https://retell-fix-test---dental-ai-backend-cszmxu7emq-uw.a.run.app`.
       3. Via the Retell Python SDK (`retell-sdk`, already a project dependency), created a brand-new, independent Retell LLM resource (`llm_b68e8116e01c131bc01e61a541dd`) cloned from the real production LLM config (`llm_e17ba00b3a5fd46321ec6a396730`, version 16 — confirmed via `is_published`/`assigned_tags` cross-check to be the actually-live published version, not just the latest draft), with only the `list_providers` tool's URL redirected to the isolated revision. Never attached to the live agent.
       4. Created a Retell test case definition + batch test (`client.tests.create_test_case_definition` / `create_batch_test`) against that isolated LLM resource, prompting a simulated caller to ask about provider availability — this produced a real, Retell-signed HTTP call against the isolated revision.
       5. **Result: PASS.** Confirmed via the isolated revision's own Cloud Run request logs, not inferred from the Retell transcript alone — a request from Retell's own infrastructure (`userAgent: axios/1.15.2`, distinct from manual curl test traffic) hit `/api/retell/list-providers` and got back `HTTP 200` with real provider data. `_verify_retell_call()` has no code path to `200` other than a passing signature check, so this is direct, log-confirmed evidence that Retell's real signing key matches `RETELL_API_KEY` and the fix works against Retell's actual live signature scheme. (The raw signature header value itself was not recoverable — neither the app's own logging nor Cloud Run's platform request-log schema captures custom header values — but the pass/fail result did not depend on it.)
       6. **Known side effect of the test, caught and cleaned up**: the test case's `tool_mocks=[]` left every tool the simulated call invoked unmocked, not just `list_providers` — this is inherent to how Retell's `tool_mocks` works (an opt-in list of what to fake, not a denylist of what to leave live), not a bug in the test construction. This caused 3 incidental real calls to the *production* backend during the test: `lookup_patient` (read, seeded test data, no real PHI) succeeded; `get_practice_context` failed with `HTTP 405` (see flag below); `ingest_call_summary` wrote one synthetic record to `call_logs` (`call_id: "playground-call-id-001"`, `practice_id: "practice-test-001"`, no real patient data). That record was located, shown for confirmation, and deleted (`db.call_logs.delete_one(...)`, confirmed `deleted_count: 1`); a sweep of every collection with a `call_id` field confirmed no residual reference anywhere.
       7. Promoted the verified revision to 100% production traffic on 2026-08-08 ~16:00 UTC: `gcloud run services update-traffic dental-ai-backend --region us-west1 --project dental-ai-backend --to-revisions=dental-ai-backend-00079-9rx=100`, confirmed via `services describe`. Watched `/api/retell/*` production logs for several minutes immediately after promotion — no traffic landed in that window, so there's no post-promotion real-call signal yet either way; worth a normal-operations spot-check on the next real call.
     - **Monitoring gap (documented, not yet fixed)**: the existing Cloud Run alert policy fires on 5xx ratio; a `RETELL_API_KEY` mismatch would produce 401s, which that alert would not catch. No change made — flagging for a future task.
     - **Separate, pre-existing, unrelated bug flagged for a future task, not investigated**: `get_practice_context` → `POST /api/practice/me` returned `HTTP 405 Method Not Allowed` during the live verification test. Unrelated to the signature fix (that tool uses the static `x-retell-api-key` shared-secret mechanism, not HMAC signing) — needs its own investigation.
     - **Known, expected test-suite side effect (still pending)**: 26 existing tests across `test_multi_tenant_isolation.py` (5) and `test_retell_hard_suite.py` (21) fail because they call these endpoints without sending a signature — correct, intended consequence of the fix, not a bug in it. Needs a follow-up (send a real signature via the same `sign()` pattern used to verify this fix) — not done yet.
  2. **STATUS: OPEN, not yet addressed.** Real MongoDB Atlas credentials hardcoded in plaintext, committed to git: `backend/scripts/create_admin.py`, `init_db.py`, `add_booking_key_index.py` all contain the live DB username/password. Needs rotating in Atlas and removing from these files.
  - **STATUS: OPEN, not yet addressed.** Moderate: `POST /api/llm/chat/completions` (the real LLM proxy, real cost) has no auth — confirmed live reachable without credentials. Cost-abuse risk, not a PHI risk.
  - Full audit also confirmed a long list of things working correctly: practice-scoping (read + write) genuinely enforced live, super_admin gates reject non-super_admin tokens live, admin endpoints reject unauthenticated requests live, no stack-trace/internal leakage on any tested error condition, CORS correctly allow-listed, `password_hash` never exposed anywhere in the codebase (audited fully), and the `/auth/login` rate limiter genuinely works under load (99.8% of a flood correctly got `429`). Load-tested `/health/ready` and `/api/billing/plans` at ~140 req/s for 60s each — stable, p99 ≈ 250ms, no errors.
- None otherwise. Stripe checkout being broken for Basic/Professional (their Products were `active=False` in the test-mode account) is fixed — new, active, correctly-priced Stripe Price objects were created and configured in `.env` as part of this session's pricing correction sweep; confirmed live via direct API query and via the 3 previously-failing checkout tests now passing. MongoDB Atlas payment (previously flagged here as suspending 07/31/26) is reactivated — independently verified via a live connection check on 2026-08-07 (ping + query against `practices` succeeded, returned 4 documents). If this file goes stale again, re-verify with a direct connection check rather than trusting this line — that's exactly how the previous stale warning happened.

---

## Recent Commits (Last 10)
```
cf5173cf fix(retell): enforce signature verification on all 7 custom-function endpoints
75229906 docs: update HANDOFF.md — Retell verification options investigated
e180137e docs: update HANDOFF.md — Retell auth fix written and locally verified, not deployed
c8c8deac docs: add Workflow Rule #13 — report in full detail, not summarized
063b4a86 docs: update HANDOFF.md — security/leakage/load audit summary
860ff136 fix(pricing): correct Basic to $499 CAD and Professional to $699 CAD across backend and frontend
e72b9b2b docs: update HANDOFF.md
b0a7d23a feat(pricing): add Coming Soon state for locked Professional tier on pricing/landing pages and onboarding wizard
ba4b66d2 docs: update HANDOFF.md
a4f7589a feat(signup): gate self-serve registration behind SELF_SERVE_TIERS_ENABLED, close direct-URL bypass to locked tiers
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
