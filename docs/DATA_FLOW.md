# PHI Data Flow Diagram
**Applies to:** Dental AI Backend (dental-ai-backend)
**Jurisdiction:** Canada — PIPEDA
**Last updated:** 2026-05-30

---

## 5.1 PHI Entry Points

PHI enters the system through three channels:

### Incoming calls via Retell

- **What enters:** Caller phone number (from_number), caller name (if matched in DB), appointment reason (spoken by caller).
- **How:** Retell initiates a webhook to `POST /api/retell/webhook` on each call event. The backend receives the call object, looks up the patient by phone number, and passes practice-specific context back to the Retell AI agent via the dynamic variables endpoint.
- **Scope enforcement:** Patient lookup is scoped to `practice_id` derived from the Retell agent's configuration — never across practices.

### Practice staff input via frontend

- **What enters:** Patient demographics (name, phone, email, date of birth, address, postal code), appointment details, provider assignments, insurance details.
- **How:** Frontend calls authenticated REST endpoints (`POST /api/patients`, `POST /api/appointments`, etc.). All endpoints require a valid JWT; `practice_id` is derived from the JWT, never from the request body.
- **Scope enforcement:** `require_practice_scope()` dependency on all patient/appointment routes.

### Insurance verification flows

- **What enters:** Insurance policy number, health card number, member ID, group number, provider name.
- **How:** Staff submit insurance details via `PUT /api/patients/:id` or the insurance verification endpoint. Data is stored in the `patients` collection under the practice's scope.

---

## 5.2 Internal Data Flow

```
Caller / Browser
      │
      ▼
[Cloud Run — FastAPI Backend]
      │
      ├── RequestLoggingMiddleware
      │     • Logs method, path, status, latency only
      │     • Never logs request bodies
      │     • PHI is never written to application logs (redact_phi() enforced)
      │
      ├── JWT Validation (get_current_user)
      │     • Validates signature, expiry, is_active
      │     • Derives practice_id from token — never from request body
      │
      ├── Business Logic (routers)
      │     • All DB queries include {"practice_id": practice_id}
      │     • Audit events written to audit_logs (resource IDs only, no PHI content)
      │     • Security events written to security_events
      │
      └── MongoDB Atlas (primary storage)
            • patients, appointments, providers, call_logs, audit_logs, etc.
            • All collections tenant-scoped by practice_id
```

**PHI is never written to application logs.** The `redact_phi()` helper in `utils/phi_redaction.py` replaces PHI field values with `[REDACTED]` before any dict is passed to the logger. The `RequestLoggingMiddleware` logs only structural request metadata (path, method, status, latency) — never request or response bodies.

**Audit logs reference resource IDs only.** The `audit_logs` schema stores `resource_id` (e.g., `patient_id`, `appointment_id`) and `action` — not the patient's name, phone number, or clinical data.

---

## 5.3 PHI Exit Points (Third-Party Services)

| Service | What PHI is sent | Purpose | Data processing agreement |
|---|---|---|---|
| **MongoDB Atlas** | Full patient and appointment records | Primary persistent storage | Yes — MongoDB Atlas DPA covers all data |
| **OpenAI** | Redacted prompts only — patient names and phones replaced with placeholders before sending | AI receptionist reasoning (default provider) | **Confirm:** OpenAI DPA / BAA must be in place before onboarding live clinic data |
| **Anthropic (Claude)** | Redacted prompts only | AI reasoning fallback (escalation provider) | **Confirm:** Anthropic DPA must be in place before onboarding live clinic data |
| **Groq** | Redacted prompts only | Fast inference (alternative provider) | **Confirm:** Groq DPA must be in place before onboarding live clinic data |
| **Retell** | Caller audio and live transcripts | Voice call handling and AI receptionist delivery | **Confirm:** Retell DPA / BAA must be in place before onboarding live clinic data |
| **Stripe** | Billing contact data only (email, name for invoice) — no clinical PHI | Subscription billing and payment processing | Yes — Stripe DPA covers billing data |

### Action required before live clinic onboarding

The following DPAs/BAAs must be confirmed in place with each provider before any real patient data is processed:

- [ ] **OpenAI** — execute Data Processing Addendum (available at platform.openai.com/docs/privacy)
- [ ] **Anthropic** — confirm data processing agreement covers API usage
- [ ] **Groq** — confirm DPA covers inference API usage
- [ ] **Retell** — execute BAA or DPA covering call audio and transcripts

This is a PIPEDA requirement: organisations must have contractual protections in place before transferring personal information to a third party for processing.

---

## 5.4 Data Residency

### Current deployment

| Component | Region | Location |
|---|---|---|
| Cloud Run (backend) | `us-west1` | Oregon, USA |
| MongoDB Atlas | TBC — confirm cluster region | TBC |

### Canadian data residency requirements

Canadian dental regulations and PIPEDA do not impose an absolute data-residency requirement for all personal information. However:

- Several provincial colleges recommend or require that patient health records be stored in Canada.
- PIPEDA requires that personal information be protected with comparable safeguards regardless of where it is stored, and that individuals be informed if their data is transferred outside Canada.
- Some dental practice management software markets itself on "data stays in Canada" as a trust differentiator.

**Before onboarding any live clinic with Canadian patient data:**

1. Confirm whether the practice's provincial regulatory college requires Canadian data residency.
2. If required: migrate Cloud Run to `northamerica-northeast1` (Montreal) and confirm the MongoDB Atlas cluster is in a Canadian region (`ca-central-1` on AWS or equivalent).
3. Update the privacy notice / consent form to disclose cross-border transfers if data remains in `us-west1`.

To check current Cloud Run region:
```bash
gcloud run services describe dental-ai-backend \
  --project dental-ai-backend \
  --format="value(metadata.labels['cloud.googleapis.com/location'])"
```

---

## Related Documents

- [SECURITY.md](SECURITY.md) — PHI handling and redaction controls
- [RETENTION.md](RETENTION.md) — Data retention policy
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Breach notification procedures
- [SECRETS.md](SECRETS.md) — Third-party API key inventory
