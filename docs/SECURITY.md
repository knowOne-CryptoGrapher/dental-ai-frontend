# Security Controls — Dental AI Backend

This document describes the SOC 2–aligned security controls implemented in the backend.

---

## 1. Authentication & Authorization

### JWT Contents
All tokens issued by the API include:

| Claim | Description |
|---|---|
| `sub` | User ID (UUID). Hard-rejected if absent. |
| `practice_id` | Tenant scope. `null` for super_admin only. |
| `role` | One of `admin`, `staff`, `provider`, `auditor`, `super_admin`. |
| `exp` | Expiry timestamp (UTC). Default 7 days; impersonation tokens 1 hour. |

Tokens issued before the `practice_id`/`role` claims were added are still accepted (grace period), but emit a WARNING log so stale sessions are visible in Cloud Logging. Re-login mints a compliant token.

### FastAPI Dependencies

| Dependency | Where | What it enforces |
|---|---|---|
| `get_current_user()` | All protected routes | Validates JWT signature, expiry, and that the DB user is active. |
| `require_role(*roles)` | Role-restricted routes | User's role must be in the allowed list; `super_admin` always passes. |
| `require_practice_scope()` | Practice-scoped routes | Rejects requests where `practice_id` is null (except super_admin). |

### Tenant Isolation
- Every DB query against `patients`, `appointments`, `providers`, `call_logs`, `audit_logs`, `analytics_events`, `locations` **must** include `{"practice_id": practice_id}` in the filter.
- `practice_id` is **always derived from the authenticated JWT / DB user**, never from a client-supplied request body field. Create models (`AppointmentCreate`, `PatientCreate`, etc.) deliberately omit `practice_id`.
- Super-admin impersonation issues a 1-hour JWT scoped to the target practice. Every impersonation action is written to `audit_logs`.

---

## 2. Logging & Audit Trails

### Structured JSON Logging
All log output is JSON (via `python-json-logger`) to stdout, parsed by Cloud Logging. Every line includes at minimum:

```json
{
  "timestamp": "2026-05-30T14:22:01Z",
  "level": "INFO",
  "logger": "routers.appointment_router",
  "message": "http_request",
  "request_id": "a3f1bc9e",
  "method": "POST",
  "path": "/api/appointments",
  "status_code": 200,
  "latency_ms": 42.1
}
```

The `RequestLoggingMiddleware` in `server.py` assigns a random `request_id` to every request and appends it as the `X-Request-ID` response header. Path, method, status, and latency are logged — **never** request bodies.

### Audit Logs (`audit_logs` collection)
Key actions are written to `db.audit_logs` via `log_audit_event()` in `auth.py`:

| Action | Trigger |
|---|---|
| `appointment_created` | POST /api/appointments |
| `appointment_cancelled` | DELETE /api/appointments/:id |
| `patient_created` | POST /api/patients |
| `patient_deleted` | DELETE /api/patients/:id |
| `practice_config_updated` | PUT /api/practice/:id/config |
| `user_invited` | POST /api/auth/invite |
| `practice_impersonated` | POST /api/superadmin/impersonate/:id |

Schema: `{ id, user_id, practice_id, action, resource_type, resource_id, details, timestamp, ip_address }`

### Security Events (`security_events` collection)
`log_security_event()` in `auth.py` writes to `db.security_events` and emits a `WARNING` with `event_category: security`. Cloud Logging alert policies can filter on this field.

| event_type | Trigger |
|---|---|
| `login_failed` | Wrong email or password |
| `login_disabled_account` | Login attempt on deactivated account |

To add more: call `await log_security_event("cross_practice_attempt", user_id=..., practice_id=..., ip_address=..., details={...})` from any router.

---

## 3. PHI Handling & Redaction

### What counts as PHI
Patient name, phone, email, date of birth, insurance policy/group numbers, emergency contact details, clinical notes, and AI call transcripts.

### Log redaction rules
1. **No PHI in HTTP request logs** — the middleware logs path/method/status/latency only.
2. **`redact_phi(dict)`** in `utils/phi_redaction.py` replaces PHI field values with `[REDACTED]`. Use this before logging any patient document.
3. **`mask_phone(phone)`** returns `***1234` for inline f-string logs.
4. Retell webhook logs emit only structural keys (e.g. `call_id`, `patient_id`) — never names, phone numbers, or transcript content.
5. AI transcripts stored in `call_logs.transcript` are labelled PHI and covered by the 7-year retention policy in the `Practice` model.

### PHI in AI flows
- The Retell AI agent receives patient data via its system prompt. Prompts are built from DB data scoped to the caller's `practice_id` — never mixing data across practices.
- Transcripts sent to Groq / OpenAI are covered by their BAA. See `ai_service.py`.
- Any stored prompt or transcript must be treated as PHI for retention and access purposes.

---

## 4. Secrets & Configuration

All sensitive values are stored in **GCP Secret Manager** and injected at runtime via `secretKeyRef` in `service.yaml`. Non-sensitive values are plain `value:` env vars.

See [docs/SECRETS.md](SECRETS.md) for the full secret inventory and rotation procedure.

---

## 5. Health Endpoints

| Endpoint | Type | Returns |
|---|---|---|
| `GET /health/live` | Liveness | `{"status": "ok"}` — always 200 if process is running |
| `GET /health/ready` | Readiness | `{"status": "ready", "db": "ok"}` — 200 only if MongoDB ping succeeds; 503 otherwise |
| `GET /health` | Legacy | Preserved for backward compatibility |

`service.yaml` wires `/health/ready` as the startup probe and `/health/live` as the liveness probe, so Cloud Run gates traffic until MongoDB is reachable and kills unhealthy instances.

Neither endpoint exposes version numbers, stack traces, or internal state beyond the `db` flag.

---

## 6. Tenant Isolation Enforcement Checklist

When adding a new endpoint that reads or writes tenant data:

- [ ] Derive `practice_id` from `current_user.get("practice_id")` — never from request body.
- [ ] Include `{"practice_id": practice_id}` in every DB query filter.
- [ ] Use `Depends(require_practice_scope())` if the endpoint must reject super-admins without explicit practice context.
- [ ] Log the action via `log_audit_event()` if it mutates data.
- [ ] Ensure any log messages use IDs (`patient_id`, `appointment_id`) — not names or phone numbers.
