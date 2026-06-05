# Security Implementation — Addendum Package
**Applies to:** Dental AI Backend (dental-ai-backend)
**Purpose:** Additions to the SOC 2 security implementation already in progress.
**Instructions for Claude Code:** Implement these additions alongside the existing security work. Do not duplicate anything already built — these are additive only.

---

## Addition 1 — Rate Limiting on Auth Endpoints (Section A)

Add rate limiting to authentication endpoints to prevent credential stuffing.

### Requirements:
- `POST /auth/login` — max 5 attempts per IP per 15 minutes, then temporary block
- `POST /auth/refresh` — max 20 requests per hour per user
- Blocked requests return `429 Too Many Requests` with a `Retry-After` header
- Rate limit state can be stored in-memory for now (Redis optional later)
- Failed attempts are logged as security events with IP and endpoint

### Implementation notes:
- Use `slowapi` (FastAPI-compatible rate limiter) or implement a simple in-memory counter
- Apply limits as FastAPI dependencies so they compose with `require_auth()`
- Log every 429 response as a security event with `event_type="rate_limit_exceeded"`

---

## Addition 2 — Log Retention Policy (Section B)

Add an explicit log retention policy document. An SOC 2 auditor will ask for this.

### Create: `docs/RETENTION.md`

Content must specify:
- **Audit logs** (`audit_logs` collection): minimum 7 years — required by Canadian dental records legislation
- **Security event logs**: minimum 1 year
- **Application/request logs** (Cloud Logging): minimum 90 days
- **Call transcripts** (if stored): maximum 90 days unless legally required longer, then anonymized after that window
- **How retention is enforced**: TTL indexes on MongoDB collections where applicable, Cloud Logging retention settings in GCP

Include instructions for setting a TTL index on application logs:
```python
# Example TTL index for application logs (90 days)
db.application_logs.create_index("timestamp", expireAfterSeconds=7776000)

# Audit logs — NO TTL index, retained indefinitely (7yr minimum)
# Security events — TTL of 1 year
db.security_events.create_index("timestamp", expireAfterSeconds=31536000)
```

---

## Addition 3 — Extended PHI Field Coverage (Section C)

Extend the PHI redaction helper to cover Canadian-specific identifiers in addition to the base set.

### Add these fields to the redaction helper:
```python
PHI_FIELDS = {
    # Base set (already in spec)
    "name", "first_name", "last_name",
    "phone", "email",
    "date_of_birth",
    # Canadian-specific additions
    "sin",                  # Social Insurance Number
    "health_card_number",   # Provincial health card
    "health_card",          # Alternate field name
    "policy_number",        # Insurance policy number
    "member_id",            # Insurance member ID
    "address",              # Street address
    "street_address",
    "postal_code",          # Indirect identifier under PIPEDA
    "city",                 # When combined with other fields, indirect identifier
}
```

### Why this matters:
Canadian PIPEDA defines personal information more broadly than US HIPAA. Indirect identifiers (address, postal code) count as personal information when they can be combined with other data to identify an individual. An auditor reviewing for Canadian compliance will check for these.

---

## Addition 4 — Incident Response Documentation (Section D)

Create `docs/INCIDENT_RESPONSE.md` covering the following sections:

### 4.1 Secret Rotation Procedures
Step-by-step instructions for rotating each secret on incident:

- **MONGODB_URI**: Generate new Atlas credentials → update Secret Manager → redeploy Cloud Run service → verify connectivity → revoke old credentials
- **JWT_SECRET**: Generate new secret → update Secret Manager → redeploy → note: rotation immediately invalidates ALL active sessions (users must re-login)
- **OPENAI_API_KEY / ANTHROPIC_API_KEY / GROQ_API_KEY**: Revoke in provider dashboard → generate new → update Secret Manager → redeploy
- **STRIPE_SECRET**: Revoke in Stripe dashboard → generate new → update Secret Manager → redeploy → verify webhook signatures
- **RETELL_API_KEY**: Revoke in Retell dashboard → generate new → update Secret Manager → redeploy

### 4.2 Emergency JWT Invalidation
Document the procedure for invalidating all active sessions immediately:
```
1. Generate new JWT_SECRET value
2. Update in Secret Manager: gcloud secrets versions add JWT_SECRET --data-file=-
3. Redeploy Cloud Run: gcloud run deploy dental-ai-backend --region ...
4. All existing tokens are immediately invalid — users must re-authenticate
5. Log the event in superadmin_audit_log with reason and timestamp
```

### 4.3 Access Control
Document who has access to Secret Manager (by role, not name in the doc — names go in a separate internal access register):
- GCP Project Owner
- GCP Secret Manager Admin role holders
- Cloud Run service account (read-only, specific secrets only)

### 4.4 Breach Notification Timeline
Under Canadian law (PIPEDA breach of security safeguards regulations):
- **Immediately:** Contain the breach, preserve evidence
- **Within 72 hours:** Notify the Office of the Privacy Commissioner of Canada if there is real risk of significant harm
- **As soon as feasible:** Notify affected individuals
- **Ongoing:** Maintain a breach record for 24 months

---

## Addition 5 — Data Flow Diagram (Section F — new deliverable)

Create `docs/DATA_FLOW.md` documenting where PHI enters, moves through, and exits the system.

### Required sections:

**5.1 PHI Entry Points**
- Incoming calls via Retell (caller name, phone number, appointment reason)
- Practice staff input via frontend (patient records, appointments)
- Insurance verification flows (patient insurance details)

**5.2 Internal Data Flow**
- FastAPI backend receives PHI → validates tenant scope → stores in MongoDB Atlas (Canada region — confirm this)
- PHI is never written to application logs (redaction layer enforced)
- Audit logs reference resource IDs only, not PHI content

**5.3 PHI Exit Points (third-party services)**
Document each external service that receives any PHI:

| Service | What PHI is sent | Purpose | Data processing agreement in place? |
|---|---|---|---|
| MongoDB Atlas | Full patient/appointment records | Primary storage | Yes — Atlas DPA |
| OpenAI | Redacted prompts only (placeholders) | AI receptionist reasoning | Confirm — OpenAI DPA |
| Anthropic (Claude) | Redacted prompts only | AI reasoning fallback | Confirm — Anthropic DPA |
| Groq | Redacted prompts only | Fast inference | Confirm — Groq DPA |
| Retell | Caller audio, transcripts | Voice call handling | Confirm — Retell DPA |
| Stripe | Billing data only (no clinical PHI) | Subscription billing | Yes — Stripe DPA |

**Action item:** Confirm Data Processing Agreements are in place with OpenAI, Anthropic, Groq, and Retell before onboarding live clinic data. This is a PIPEDA requirement.

**5.4 Data Residency Note**
Current Cloud Run deployment: `us-west1` (Oregon, USA).
Canadian dental regulations and PIPEDA may require patient data to remain in Canada.
**Before onboarding any live clinic:** confirm data residency requirements and migrate to `northamerica-northeast1` (Montreal) if required.

---

## Addition 6 — Secret Manager Migration (Section D — P0 action)

The existing spec says "verify secrets are in Secret Manager" but the current state is that `MONGODB_URI` and other secrets are plain Cloud Run environment variables. This must be fixed — plain env vars are visible to anyone with Cloud Run IAM access.

### Migration steps for Claude Code to implement:

**Step 1 — Create secrets in Secret Manager:**
```bash
# Run these in the terminal — replace values with actuals from backend/.env
echo -n "mongodb+srv://..." | gcloud secrets create MONGODB_URI --data-file=- --project dental-ai-backend
echo -n "your-jwt-secret" | gcloud secrets create JWT_SECRET --data-file=- --project dental-ai-backend
echo -n "sk-..." | gcloud secrets create OPENAI_API_KEY --data-file=- --project dental-ai-backend
echo -n "sk-ant-..." | gcloud secrets create ANTHROPIC_API_KEY --data-file=- --project dental-ai-backend
echo -n "gsk_..." | gcloud secrets create GROQ_API_KEY --data-file=- --project dental-ai-backend
echo -n "sk_live_..." | gcloud secrets create STRIPE_SECRET --data-file=- --project dental-ai-backend
echo -n "key_..." | gcloud secrets create RETELL_API_KEY --data-file=- --project dental-ai-backend
```

**Step 2 — Grant Cloud Run service account access:**
```bash
gcloud secrets add-iam-policy-binding MONGODB_URI \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor" \
  --project dental-ai-backend
# Repeat for each secret
```

**Step 3 — Update service.yaml to reference Secret Manager:**
```yaml
env:
  - name: MONGODB_URI
    valueFrom:
      secretKeyRef:
        name: MONGODB_URI
        key: latest
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: JWT_SECRET
        key: latest
  # Repeat for all secrets
```

**Step 4 — Remove plain env vars from Cloud Run:**
```bash
gcloud run services update dental-ai-backend \
  --remove-env-vars MONGODB_URI,JWT_SECRET,OPENAI_API_KEY,ANTHROPIC_API_KEY,GROQ_API_KEY,STRIPE_SECRET,RETELL_API_KEY \
  --region us-west1 \
  --project dental-ai-backend
```

**Step 5 — Redeploy and verify:**
```bash
gcloud run deploy dental-ai-backend \
  --image gcr.io/dental-ai-backend/dental-ai-backend \
  --platform managed \
  --region us-west1 \
  --project dental-ai-backend
```

Verify health endpoint returns 200 after migration.

---

## Summary of new files to create

| File | Purpose |
|---|---|
| `docs/RETENTION.md` | Log and data retention policy |
| `docs/INCIDENT_RESPONSE.md` | Secret rotation and breach response procedures |
| `docs/DATA_FLOW.md` | PHI entry, movement, and exit points |

## Summary of code changes

| Area | Change |
|---|---|
| `auth/rate_limiter.py` (new) | Rate limiting for login and refresh endpoints |
| `auth/router.py` | Apply rate limiter dependencies to login and refresh |
| `utils/phi_redaction.py` | Extend PHI fields with Canadian-specific identifiers |
| `service.yaml` | Migrate secrets from plain env vars to Secret Manager refs |
