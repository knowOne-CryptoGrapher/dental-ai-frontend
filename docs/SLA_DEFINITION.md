# SLA Definition Document — Founding Clinic Program

> **DRAFT — NOT LEGAL ADVICE — FOR LAWYER REVIEW BEFORE USE**
>
> This document is a companion to the Clinic Service Agreement and is drafted from verified product, code, and live monitoring-infrastructure facts as of 2026-09-15. It is not a substitute for review by qualified counsel and must not be sent to, or signed by, a real clinic until reviewed and approved by a lawyer. The figures and commitments below are proposed defaults for lawyer review, not final locked terms — several are stated as decisions being made now rather than claims about an existing track record, and are marked accordingly.

**Between:** Simplex Dental Intelligence & Reception Systems Inc., operating as Front Desk Dental AI ("**Simplex Dental**")
**And:** [Clinic Legal Name] ("**Clinic**")
**Applies to:** the Service as defined in the Clinic Service Agreement, Section 2.

---

## 1. Scope

1.1 This SLA applies to the Front Desk Dental AI Service as provisioned under the Clinic's `founding_clinic_basic` plan: the AI receptionist call-handling platform, patient lookup, appointment management, and call log/dashboard functionality.

1.2 This SLA does not apply to features not included in the Clinic's plan, including full insurance/claims processing (blocked at the API level for this plan regardless of any preview flag), analytics, or multi-location support.

1.3 This SLA does not apply to outages or degradation caused by third-party services outside Simplex Dental's control — see Section 6 (Exclusions).

---

## 2. Uptime Target

2.1 Simplex Dental commits to a target of 99% monthly uptime for the Service. This is a forward-looking commitment being made now, not a claim based on historical track record: the production monitoring infrastructure that measures uptime (Cloud Run error-rate alerting and its notification channel) was only fully verified and made functional this session, and no meaningful historical measurement period exists yet behind this number. Prior internal load testing ("25 workers, all invariant checks passing") is synthetic load-test data and is not evidence of real-world uptime.

2.2 This target is measured via infrastructure confirmed live today: a Cloud Run uptime check on `/health/ready` (verifies database connectivity, not just process liveness) at 5-minute intervals, and an error-rate alert policy (fires when 5xx responses exceed 5% of traffic over a 5-minute window, with a minimum 20-request volume gate) — both confirmed enabled, with the alert's notification channel confirmed verified and functional this session.

---

## 3. Support Response Times

3.1 Support is provided on a best-effort basis via support@frontdeskdentalai.com, as described in the Clinic Service Agreement, Section 9.

3.2 This is a deliberate decision for the current founding-clinic-scale launch, not an oversight: no formal response-time tiers (e.g., "Priority 1 within 4 hours") are committed to at this stage, because no ticketing system, on-call process, or response-time tracking infrastructure exists yet to calibrate real tiers against. This is intended to be revisited once real support volume exists to inform what commitments are actually achievable — not left indefinitely undefined.

---

## 4. Incident/Outage Communication

4.1 Simplex Dental maintains an internal incident detection and response process for security/privacy breaches, described in `docs/INCIDENT_RESPONSE.md` (PIPEDA-scoped: containment, 72-hour OPC notification target, individual notification, 24-month breach record retention). That process is specific to privacy/security breaches under PIPEDA and is distinct from general service-outage communication.

4.2 For any Service outage expected to exceed [⚠️ **threshold to be decided — e.g., "2 hours"**], Simplex Dental will send email notification to the Clinic's contact on file, using Simplex Dental's existing Amazon SES email infrastructure (already in live production use for other account notifications). The specific outage-duration threshold that triggers this notification has not yet been set and needs Darnell's decision; the notification mechanism itself — SES email to the Clinic's contact on file — is decided and is genuinely available today, not aspirational.

---

## 5. Maintenance Windows

5.1 Where practical, Simplex Dental will provide advance notice of scheduled maintenance to the Clinic's contact on file.

5.2 Where feasible, scheduled maintenance will be performed outside normal business hours.

5.3 No specific advance-notice period (e.g., "at least 48 hours") is locked in at this time. ⚠️ Flagging this as a number worth deciding rather than leaving permanently general — a specific commitment here is easy to add later and would strengthen this section, but isn't invented here since no existing practice or precedent informs what's realistic.

---

## 6. Exclusions

6.1 This SLA does not apply to unavailability caused by:
- Outages or degradation of third-party subprocessors the Service depends on, including MongoDB Atlas (primary data storage), Stripe (billing), Amazon SES (email), and, for AI reasoning, Groq (default) or Anthropic (escalation) — see `docs/DPA_REGISTER.md` for the current full subprocessor list.
- Google Cloud Platform outages affecting Cloud Run or related infrastructure.
- Circumstances beyond Simplex Dental's reasonable control (force majeure) — [standard force majeure language to be finalized by counsel].
- Scheduled maintenance performed consistent with Section 5.

6.2 Retell (voice call handling) is a named subprocessor per `docs/DPA_REGISTER.md`, currently the sole handler of live inbound/outbound call audio — an outage of Retell's infrastructure would materially affect the Service's core call-answering function specifically, distinct from the other listed subprocessors. Worth calling out explicitly given how central it is to what the Clinic is actually paying for.

---

## 7. Remedies

**[RESERVED — TO BE DRAFTED BY COUNSEL / PENDING REFUND INFRASTRUCTURE.]** No service-credit mechanism, refund-on-SLA-breach clause, or any other remedy structure exists in code, billing logic, or documentation today — confirmed this session that Stripe refund logic itself is not implemented (`backend/HANDOFF.md`'s Pending list, updated this session to reflect that this specifically blocks this section). This section cannot be responsibly drafted until that decision is made and, if credits are involved, until the underlying billing capability to issue them actually exists.

---

## Traceability appendix — source for every factual claim above

| Section | Claim | Source |
|---|---|---|
| 1.1, 1.2 | Plan scope (included/excluded features) | `backend/plans.py`, `founding_clinic_basic` entry |
| 2.1 | 99% target framed as forward-looking, not track record | Decision made explicitly for this document; framing matches this session's confirmed finding that no historical uptime data exists |
| 2.2 | Live monitoring infrastructure (uptime check, error-rate policy, verified channel) | This session — `gcloud alpha monitoring channels/policies describe`, raw REST verification of `verificationStatus: VERIFIED` |
| 3.1, 3.2 | Best-effort support, no formal tiers, framed as deliberate | Decision made explicitly for this document; underlying infrastructure gap confirmed via full codebase search (only `support@frontdeskdentalai.com` found, no ticketing) |
| 4.1 | `docs/INCIDENT_RESPONSE.md` scope (PIPEDA breach process) | Reviewed extensively this session during the PHIPA/PIPEDA checklist work |
| 4.2 | SES as the notification mechanism | Confirmed live in production this session and prior — Amazon SES v2, `SES_FROM_EMAIL`/`SES_CONFIGURATION_SET` provisioned and deployed; used for existing account notification emails (`services/email_service.py`) |
| 5.1-5.3 | Maintenance window boilerplate, no locked number | Decision made explicitly for this document; no existing precedent found anywhere in code/docs |
| 6.1 | Named subprocessors | `docs/DPA_REGISTER.md`, current live register |
| 6.2 | Retell as sole call-audio handler | `docs/DPA_REGISTER.md` Retell row; consistent with this session's Retell DPA findings |
| 7 | Reserved, blocked on refund infrastructure | `backend/HANDOFF.md` Pending list — updated this session to explicitly link this blocker to this section |
