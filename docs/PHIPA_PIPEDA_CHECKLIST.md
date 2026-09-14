# PHIPA / PIPEDA / BC PIPA Compliance Checklist

> **DRAFT — NOT LEGAL ADVICE — FOR LAWYER REVIEW BEFORE RELIANCE**
>
> This document is an internal engineering-grounded checklist, not a legal opinion. It maps
> the current, actually-committed state of the codebase and legal-facing pages to PIPEDA's
> fair information principles and related BC/Ontario obligations. It is not a substitute for
> review by qualified Canadian privacy counsel, and must not be relied upon, shared with
> customers/auditors, or cited as evidence of compliance until reviewed and approved by a
> lawyer.

**Prepared:** 2026-08-09
**Sources reviewed (live, as committed today):**
- `frontend/src/pages/PrivacyPage.jsx` (Privacy Policy, v1.1, last updated July 14, 2026)
- `frontend/src/pages/TermsOfServicePage.jsx` (Terms of Service, v1.2, last updated July 14, 2026)
- `docs/DATA_FLOW.md` (last updated 2026-05-30)
- `docs/DPA_REGISTER.md` (last updated 2026-05-31)
- `docs/INCIDENT_RESPONSE.md` (last updated 2026-05-30, cross-referenced for breach readiness)
- Backend code: `backend/routers/patient_router.py`, `backend/models.py`,
  `backend/utils/phi_redaction.py`, `backend/llm/openai_provider.py`, `backend/service.yaml`

> **⚠️ Flagging before you read further:** the Privacy Policy and Terms of Service pages
> (dated July 14, 2026) are ~6 weeks newer than `DATA_FLOW.md`/`DPA_REGISTER.md`/
> `INCIDENT_RESPONSE.md` (dated May 30–31, 2026). In at least two places below, the
> public-facing Privacy Policy asserts something as an accomplished fact that the internal
> docs and code show is **not yet true**. These are marked **🔴 MATERIAL DISCREPANCY** and
> should be the lawyer's/founder's first priority, not the general principle-by-principle
> gaps.

---

## 🔴 Material discrepancies (public claims vs. actual current state)

### 1. Data residency — ✅ RESOLVED (was: Privacy Policy claimed Canadian storage before it was true)

**Status update (2026-09-14): this gap is now closed.** As of 2026-09-09 (compute) and
2026-09-11 (database), both Cloud Run and MongoDB Atlas are confirmed live in
`northamerica-northeast1` (Montreal) — not a future target. Confirmed directly, not taken on
report:
- **Compute:** `gcloud run services describe` shows the service live in
  `northamerica-northeast1`; production `GET /health/ready` reports
  `compute_region: northamerica-northeast1`.
- **Database:** a direct `hello()`/`replSetGetConfig()` query against the live Atlas cluster
  shows `region: NORTH_AMERICA_NORTHEAST_1`, `availabilityZone:
  northamerica-northeast1-a/b/c` on all 3 replica-set members, with a genuine
  state-transition signature (`setVersion` 31→38, `term` 22→23, new primary elected) — not a
  stale/cached read. Migrated in-place via Atlas's native region-edit feature (same cluster,
  same connection string, `replicaSetId` unchanged).
- **Data integrity:** a post-migration check confirmed no data loss — `practice-test-001`,
  the patient record, all 3 providers, and both original real call log transcripts intact;
  collection counts stable or grown, never shrunk.
- Full evidence trail: `docs/DPA_REGISTER.md`'s "Data Residency Confirmation" section
  (updated 2026-09-12).

`PrivacyPage.jsx` §4's *"For Canadian customers, practice and patient data are stored in
Canadian data centers"* claim is now accurate in substance.

**Original gap (for record):**

`PrivacyPage.jsx` §4 states: *"For Canadian customers, practice and patient data are stored
in Canadian data centers (e.g., ca-west or ca-east regions)."* — phrased as a present-tense,
unqualified fact.

`docs/DATA_FLOW.md` §5.4 ("Current deployment status"), however, shows this is a **target**,
not the current state, as of the Aug 9, 2026 review:

| Component | Current | Target | Status |
|---|---|---|---|
| Cloud Run | us-west1 (Oregon, **USA**) | northamerica-west2 (Calgary) | Migration required before live clinics |
| MongoDB Atlas | **TBC** | atlas-ca-west + atlas-ca-east | Confirm cluster region |

`docs/DPA_REGISTER.md` corroborates: Cloud Run east is "❌ Not deployed", Atlas cluster region
is "⏳ Confirm Atlas cluster region." Note: the user's task brief for this checklist described
this as an "actual confirmed Canada West/East cluster setup" — that framing does **not**
match what `DATA_FLOW.md` itself says. Flagging this explicitly rather than writing up the
region setup as confirmed.

The **application-level logic** for region routing is real and implemented (`home_region`
assigned per province at onboarding, immutable after creation, cross-region access blocked at
`backend/regions/db_factory.py`) — but the underlying infrastructure it routes to is not yet
in Canada. If any live (non-test) patient data exists in the system today, it is currently
being computed on in Oregon, USA, and stored in an Atlas cluster whose region is unconfirmed.

**This was resolved via the actual migration** — to `northamerica-northeast1` (Montreal),
not the originally-targeted (and never-real) Calgary — not by relabeling the Privacy Policy.

**Known residual issue, fixed separately this session:** `docs/DATA_FLOW.md` §5.4's own
tables were not updated when the migration completed and, until this session, still
described the old Oregon/Calgary/TBC state — corrected in a companion diff.

**Remaining, non-blocking note:** the app only has ONE real region today
(`northamerica-northeast1`), not the two (`ca-west`/`ca-east`) the `home_region` routing
logic is built for — a deliberate, documented future-plan gap in the code itself
(`backend/regions/region_config.py`'s own comments), not a compliance gap. No action needed
unless a genuine second region is stood up later.

### 2. Subprocessor DPAs — 🟡 PARTIALLY RESOLVED (was: 4 of 7 not started)

`PrivacyPage.jsx` §8 states: *"Each provider acts as our processor or sub-processor and is
bound by appropriate data processing and security agreements."* — again, unqualified.

**Status update (2026-09-14):** real progress since the Aug 9 review, but not fully resolved.
Current status per `docs/DPA_REGISTER.md` (last updated 2026-09-12):

| Service | DPA Status |
|---|---|
| MongoDB Atlas | ✅ Executed |
| Stripe | ✅ Executed |
| Google Cloud | ✅ Executed |
| Anthropic (Claude) | ✅ Resolved — confirmed auto-incorporated into Anthropic's Commercial Terms of Service, no separate signature required (Sept 2026) |
| Retell | ⏳ Reply received — standard DPA confirmed available (covers PIPEDA; configurable retention 1-730 days; zero-retention opt-out; 60-day post-termination deletion); not yet executed via click-agreements.retellai.com |
| Groq | ⏳ Requested — awaiting response (letter sent Sept 2026) |
| OpenAI | ❌ Not started |
| Crisp | ❌ Not started — PHI exposure not yet assessed (newly identified subprocessor, added to the register Sept 2026; named in the live Privacy Policy §8 as "Chat" but had no DPA-tracking entry before this) |

**Now 2 of 8 subprocessors have no executed DPA and no DPA-in-progress** (OpenAI, Crisp) —
down from the original "4 of 7." Retell and Groq have moved from "not started" to
active/in-progress; Anthropic is fully resolved. Crisp is a newly-identified subprocessor not
covered by the original Aug 9 review.

**Action still required before relying on §8 of the Privacy Policy without qualification:**
execute Retell's DPA (now available, just needs signing — still highest priority, call audio
is PHI), start OpenAI's and Crisp's DPA processes, and confirm Groq's response.

### 3. Vendor list inconsistency between documents (minor, but worth resolving)

`PrivacyPage.jsx` §8 lists only **Anthropic (Claude) and Groq (Llama 3)** under "AI
Reasoning" — OpenAI is not mentioned anywhere in the public Privacy Policy's vendor list.
`docs/DATA_FLOW.md` and `docs/DPA_REGISTER.md`, by contrast, both describe OpenAI as the
**"default provider"** for AI receptionist reasoning.

Checked directly: `backend/llm/openai_provider.py` exists and is a live, integrated provider
in the LLM router (`backend/llm/registry.py`, `backend/llm/router.py`) — it is not dead code.
Separately, `backend/service.yaml` (the actual deployed Cloud Run config) currently sets
`LLM_DEFAULT_PROVIDER=groq` and `LLM_ESCALATION_PROVIDER=anthropic`, not OpenAI — so the
`DATA_FLOW.md`/`DPA_REGISTER.md` description of OpenAI as "default" is itself stale relative
to production config. Net effect: OpenAI is not currently the default, but the code path is
live and could still route PHI-redacted prompts to it (manual override, fallback, or future
config change). The Privacy Policy's omission of OpenAI understates the actual vendor
footprint; the OpenAI DPA action item in `DPA_REGISTER.md` should **not** be closed out just
because OpenAI isn't the current default.

**Recommend:** either add OpenAI to the public vendor list (§8) for accuracy, or confirm and
document that the OpenAI code path is fully disabled/unreachable in production — whichever is
actually true — before treating this as resolved.

---

## PIPEDA — 10 Fair Information Principles

| # | Principle | Status | Grounding |
|---|---|---|---|
| 1 | **Accountability** | 🟡 Partial | Privacy Policy names a contact (`privacy@frontdeskdentalai.com`, `PrivacyPage.jsx` §13) but no named Privacy Officer/DPO is confirmed anywhere in the reviewed materials. `docs/INCIDENT_RESPONSE.md` §4.4 explicitly defers named contacts (Privacy Officer/DPO, legal counsel, CEO) to "a separate document" whose existence was not verified in this review. **Gap:** confirm this register actually exists and a specific individual is designated. |
| 2 | **Identifying Purposes** | 🟢 Implemented | `PrivacyPage.jsx` §2–3 enumerates categories collected (practice, user, patient interaction, billing, usage/analytics data) and the specific purposes for each. Matches what `docs/DATA_FLOW.md` §5.1 shows actually enters the system. |
| 3 | **Consent** | 🟡 Partial | Real mechanism exists: `PATCH /patients/{patient_id}/consent` (`backend/routers/patient_router.py:85-113`, `mark_consent_given`) sets `consent_given`, `consent_date`, `consent_method` (`backend/models.py:217-219`) and writes an audit event (`patient_consent_given`). New patients default to `consent_given: False` (`patient_router.py:66`) — correct opt-in default. **However:** this is *staff-attested* consent ("consent_method": "staff_verified") — the practice attests consent was obtained from the patient, not a patient-facing consent capture flow owned by Dental AI. That's consistent with the Privacy Policy's processor framing (§1, §5, §9 — practice is responsible for patient-facing notices/consent), but should be confirmed with counsel as sufficient. **Gap:** no consent-withdrawal endpoint found (only "mark given"); Privacy Policy §9 promises a right to "withdraw consent" but there is no corresponding API. |
| 4 | **Limiting Collection** | 🟢 Implemented | `docs/DATA_FLOW.md` §5.1 documents the three PHI entry points (Retell webhook, staff frontend input, insurance flows) and scopes collection to what's needed for each. All patient/appointment routes enforce `require_practice_scope()`; `practice_id` is derived from JWT, never request body. No over-collection observed in the fields reviewed. |
| 5 | **Limiting Use, Disclosure, and Retention** | 🔴 Gap | Privacy Policy §7 promises practice-configurable retention (default 7 years) and deletion/anonymization "after the configured retention period... from active systems and backups." **No retention-period field, scheduled purge job, or anonymization routine was found anywhere in `backend/`** (searched for `retention_period`, `purge`, `anonymize` — zero matches outside `HANDOFF.md` prose). What exists is a manual, single-record hard delete: `DELETE /patients/{patient_id}` (`patient_router.py:137-140`, admin-role-gated, practice-scoped). There is no whole-account/practice deletion endpoint — §7's "you may request deletion of your account at any time by contacting support" is an off-system, manual process today, not something enforced or audited in code. |
| 6 | **Accuracy** | 🟡 Partial | Staff can correct patient records via existing `PUT /api/patients/:id` (per `docs/DATA_FLOW.md` §5.1). No dedicated patient-initiated correction-request flow or audit trail distinct from a normal edit — consistent with the processor model (practice, not Dental AI, is patient-facing per §9), but worth confirming with counsel that this satisfies the accuracy principle for Dental AI's own accountability as processor. |
| 7 | **Safeguards** | 🟢 Implemented | Strong, specific mechanisms: JWT auth (`get_current_user`) validating signature/expiry/`is_active`; `require_practice_scope()` tenant isolation on every patient/appointment route; `redact_phi()` (`backend/utils/phi_redaction.py`) strips PHI fields before any dict reaches a logger; `RequestLoggingMiddleware` logs structural metadata only (method/path/status/latency), never bodies; `audit_logs` collection stores resource IDs and actions only, not PHI content; `security_events` collection for security-relevant events; encryption in transit (Privacy Policy §11). |
| 8 | **Openness** | 🟢 Implemented | `PrivacyPage.jsx` is public, plain-language, and describes data categories, purposes, vendors (§8), retention (§7), and rights (§9). Reasonably transparent in structure — see Material Discrepancies section above for where its *content* overstates current state. |
| 9 | **Individual Access** | 🔴 Gap | Privacy Policy §9 promises a right to access, correct, delete, and withdraw consent, but directs individuals to "contact your dental practice, who is typically the controller." **No self-serve data export/access-request endpoint exists in the backend** (searched for `export`, `data_export`, `download_data`, `right_to_access` — no implementation found). Fulfillment today would be entirely manual/support-driven, with no system of record for tracking SAR (subject access request) turnaround. |
| 10 | **Challenging Compliance** | 🔴 Gap | Privacy Policy §13 provides an email contact (`privacy@frontdeskdentalai.com`) as the de facto complaints channel, but no documented complaint-handling procedure, SLA, or escalation path was found in any reviewed document. |

---

## BC PIPA-Specific Requirements

- **Governing law:** `TermsOfServicePage.jsx` §12 confirms BC law and BC courts govern — consistent with a BC-only soft launch.
- **Data residency:** See **✅ Material Discrepancy #1 (RESOLVED)** above — both compute and database are now confirmed live in Canada (`northamerica-northeast1`, Montreal), as of Sept 2026. This was the single most consequential item for a BC PIPA / residency-sensitive customer base; it is now closed.
- **BC PIPA breach notification:** `docs/INCIDENT_RESPONSE.md` §4.4 documents only the **federal PIPEDA** breach notification timeline (OPC, 72-hour target, SOR/2018-64). It does not separately address BC's own breach-notification duty to BC's Office of the Information and Privacy Commissioner (OIPC) under PIPA. **Flagging for lawyer confirmation, not asserting an answer:** confirm whether, for a BC-headquartered private-sector organization, PIPEDA's "substantially similar" designation for BC means only OPC notification is required, or whether BC OIPC notification is a separate, parallel obligation that needs its own documented procedure.

---

## Breach Notification & Incident Response Readiness

`docs/INCIDENT_RESPONSE.md` is genuinely substantive, not boilerplate:
- §4.1 — concrete, tested-looking secret-rotation runbooks for every credential in the stack (Mongo URI, JWT secret, all 3 LLM provider keys, Stripe keys, Retell key), each with exact `gcloud`/PowerShell commands.
- §4.2 — an emergency JWT invalidation procedure with explicit audit-logging step.
- §4.4 — a specific PIPEDA breach notification timeline (immediate containment → 72-hour OPC target → individual notification → 24-month breach record retention), with a dental-specific "real risk of significant harm" analysis (clinical notes, health card/SIN, insurance policy numbers, financial data).

**Gaps within IR readiness itself:**
- §4.3's internal escalation contact list (Privacy Officer/DPO, legal counsel, practice owner/CEO) is explicitly deferred to "a separate internal access register" — existence not confirmed in this review. If it doesn't exist yet, the 72-hour OPC clock has no named owner to start it.
- No breach-record **template or system** was found — §4.4 describes the 24-month record-retention requirement as an obligation, but there's no implemented log/document format to fulfill it when an actual incident occurs.
- BC OIPC notification path not addressed (see BC PIPA section above).

---

## PHIPA (Ontario) — Explicitly NOT Addressed

**This checklist does not cover PHIPA.** Ontario's *Personal Health Information Protection
Act* imposes materially different obligations than PIPEDA/BC PIPA (e.g., health information
custodian designation, its own breach-notification and IPC Ontario complaint regime, different
consent rules for health information specifically). None of `PrivacyPage.jsx`,
`TermsOfServicePage.jsx`, or `docs/DATA_FLOW.md` reference PHIPA, and nothing in the reviewed
incident-response or DPA documentation was written with PHIPA in mind.

This is consistent with — and expected for — a **BC-only soft launch**. It is flagged here
explicitly rather than silently assumed covered, because `docs/DATA_FLOW.md` §5.4's own
`home_region` table already includes an Ontario/Quebec/Atlantic mapping (`ca-east`,
Montreal), meaning the region-routing code is already built in anticipation of an Ontario
expansion — well ahead of any PHIPA-specific legal review having happened.

**Action required before any Ontario expansion:** a separate PHIPA-specific compliance review
must be completed before onboarding any Ontario-based practice. Do not treat PIPEDA/BC PIPA
compliance (even once the gaps above are closed) as sufficient for Ontario.

---

## Subprocessor DPA Status (as of `docs/DPA_REGISTER.md`, 2026-09-12)

Restated directly from the register, not summarized as resolved beyond what the register
itself states:

| Service | PHI Sent | DPA Status |
|---|---|---|
| MongoDB Atlas | Full patient records | ✅ Executed |
| Stripe | Billing contact only | ✅ Executed |
| Google Cloud | Encrypted secrets only | ✅ Executed |
| Anthropic (Claude) | Redacted prompts only | ✅ Resolved — no signature needed (auto-incorporated into Commercial ToS) |
| Retell | Caller audio + transcripts | ⏳ Reply received — DPA available, not yet executed (register's own priority ranking: **highest risk — audio is PHI**) |
| Groq | Redacted prompts only | ⏳ Requested — awaiting response |
| OpenAI | Redacted prompts only | ❌ Not started |
| Crisp | Chat contents (PHI exposure not yet assessed) | ❌ Not started |

**2 of 8 subprocessors have no executed DPA and no DPA-in-progress** (OpenAI, Crisp) — down
from the original "4 of 7." Retell and Groq are now actively in progress; Anthropic is
resolved. Crisp is a newly-identified subprocessor not covered by the original Aug 9 review.

---

## Summary of Items for Lawyer Review (priority order)

1. ✅ ~~Correct or complete the data-residency claim in `PrivacyPage.jsx` §4~~ **RESOLVED (Sept 2026)** — both compute and database confirmed live in Canada; see Material Discrepancy #1 above for evidence.
2. 🟡 Execute the remaining subprocessor DPAs — Retell (available, just needs signing) and OpenAI/Crisp (not started) remain; Groq awaiting response; Anthropic resolved. Correct `PrivacyPage.jsx` §8's unqualified claim until these close.
3. 🔴 Resolve the OpenAI vendor-list inconsistency (Privacy Policy omits it; internal docs list it as default; code confirms it's live and reachable).
4. 🟡 Confirm BC PIPA/OIPC breach notification obligations are separately covered, not just PIPEDA/OPC.
5. 🟡 Confirm a named Privacy Officer/DPO and internal escalation register actually exist (referenced but not verified in this review).
6. 🔴 Close the gap between the Privacy Policy's retention/deletion promises (§7) and the actual absence of any automated retention or purge mechanism in code.
7. 🔴 Close the gap between the Privacy Policy's access-rights promise (§9) and the absence of any self-serve data-access/export mechanism.
8. 🟡 Add a consent-withdrawal endpoint, or confirm the "contact support" manual path is an acceptable substitute.
9. ⚪ PHIPA: out of scope by design for this BC-only launch — schedule a dedicated PHIPA review before any Ontario expansion.
