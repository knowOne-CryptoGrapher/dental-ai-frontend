# Incident Response Procedures
**Applies to:** Dental AI Backend (dental-ai-backend)
**Jurisdiction:** Canada — PIPEDA Breach of Security Safeguards Regulations
**Last updated:** 2026-05-30

---

## 4.1 Secret Rotation Procedures

Run these steps immediately when a secret is suspected to be compromised. All steps assume access to GCP project `dental-ai-backend` and the relevant third-party dashboards.

### MONGODB_URI

1. Log in to MongoDB Atlas → **Database Access** → create a new database user with the same permissions.
2. Copy the new connection string.
3. Add a new secret version in Secret Manager:
   ```powershell
   echo -n "mongodb+srv://NEW_USER:NEW_PASS@..." | gcloud secrets versions add MONGODB_URI `
       --data-file=- --project dental-ai-backend
   ```
4. Redeploy Cloud Run to pick up the new version:
   ```powershell
   gcloud run services replace backend/service.yaml `
       --platform managed --region us-west1 --project dental-ai-backend
   ```
5. Verify `/health/ready` returns 200.
6. Revoke the old Atlas user.

### JWT_SECRET_KEY

> **Warning:** Rotation immediately invalidates **all active user sessions**. Every logged-in user will be forced to re-authenticate on their next request. Schedule during low-traffic hours and notify users in advance where possible.

1. Generate a new secret (minimum 32 bytes of entropy):
   ```powershell
   $newSecret = [System.Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
   ```
2. Add a new version to Secret Manager:
   ```powershell
   echo -n $newSecret | gcloud secrets versions add JWT_SECRET_KEY `
       --data-file=- --project dental-ai-backend
   ```
3. Redeploy Cloud Run:
   ```powershell
   gcloud run services replace backend/service.yaml `
       --platform managed --region us-west1 --project dental-ai-backend
   ```
4. All existing tokens are immediately invalid — users must re-authenticate.
5. Log the event: write a record to `superadmin_audit_log` with `action="jwt_secret_rotated"`, reason, and timestamp.

### OPENAI_API_KEY

1. Log in to the OpenAI platform → **API keys** → create a new key.
2. Add the new key to Secret Manager:
   ```powershell
   echo -n "sk-proj-..." | gcloud secrets versions add OPENAI_API_KEY `
       --data-file=- --project dental-ai-backend
   ```
3. Redeploy Cloud Run.
4. Verify AI calls succeed (check `/health/ready` and a test inference).
5. Revoke the old key in the OpenAI dashboard.

### ANTHROPIC_API_KEY

1. Log in to console.anthropic.com → **API Keys** → create a new key.
2. Add to Secret Manager and redeploy (same pattern as OPENAI_API_KEY, secret name `ANTHROPIC_API_KEY`).
3. Revoke the old key.

### GROQ_API_KEY

1. Log in to console.groq.com → **API Keys** → create a new key.
2. Add to Secret Manager (`GROQ_API_KEY`) and redeploy.
3. Revoke the old key.

### STRIPE_SECRET_KEY

1. Log in to dashboard.stripe.com → **Developers → API keys** → **Roll** the secret key.
2. Copy the new `sk_live_...` value.
3. Add to Secret Manager (`STRIPE_SECRET_KEY`) and redeploy.
4. Verify billing endpoints return correct responses (subscription creation, webhook delivery).
5. The old key is automatically invalidated by Stripe's roll operation.

> **Note:** Stripe restricted keys (if used) must be rolled separately.

### STRIPE_WEBHOOK_SECRET

1. In the Stripe dashboard → **Developers → Webhooks** → select the endpoint → **Reveal signing secret** → **Roll**.
2. Add the new `whsec_...` value to Secret Manager (`STRIPE_WEBHOOK_SECRET`) and redeploy.
3. Verify webhook delivery succeeds (check Stripe's webhook log for 200 responses after rotation).

### RETELL_API_KEY

1. Log in to the Retell dashboard → **Settings → API Keys** → revoke the current key and generate a new one.
2. Add to Secret Manager (`RETELL_API_KEY`) and redeploy.
3. Verify inbound call routing and webhook delivery.

---

## 4.2 Emergency JWT Invalidation

Use this procedure when a JWT signing key compromise is confirmed or strongly suspected, or when a super-admin account is believed to be hijacked.

```
1. Generate a new JWT_SECRET_KEY value (see section 4.1 above).

2. Update in Secret Manager:
   gcloud secrets versions add JWT_SECRET_KEY --data-file=- --project dental-ai-backend
   (pipe the new value via stdin)

3. Redeploy Cloud Run immediately:
   gcloud run services replace backend/service.yaml \
     --platform managed --region us-west1 --project dental-ai-backend

4. All existing tokens are immediately invalid.
   Users must re-authenticate — there is no grace period.

5. Log the incident in the superadmin audit log:
   { action: "emergency_jwt_invalidation", reason: "<reason>", rotated_by: "<email>", timestamp: <UTC> }

6. Notify affected users if the compromise was due to a data breach (see section 4.4).
```

---

## 4.3 Access Control

The following roles have access to GCP Secret Manager for project `dental-ai-backend`. Names are maintained in a separate internal access register (not in this document) so this file can be shared without disclosing personnel.

| Role | Access level |
|---|---|
| GCP Project Owner | Full Secret Manager admin |
| GCP Secret Manager Admin role holders | Can create, update, and delete secrets |
| Cloud Run service account (`244697312574-compute@developer.gserviceaccount.com`) | `roles/secretmanager.secretAccessor` on specific secrets only (read-only, no version management) |

To verify current IAM bindings for a secret:
```bash
gcloud secrets get-iam-policy MONGODB_URI --project dental-ai-backend
```

To list all Secret Manager IAM bindings across secrets:
```bash
for secret in MONGODB_URI JWT_SECRET_KEY OPENAI_API_KEY ANTHROPIC_API_KEY GROQ_API_KEY RETELL_API_KEY STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET; do
  echo "=== $secret ==="; gcloud secrets get-iam-policy $secret --project dental-ai-backend; done
```

---

## 4.4 Breach Notification Timeline

Under the **PIPEDA Breach of Security Safeguards Regulations** (SOR/2018-64), the following timeline applies when a breach of security safeguards is identified that creates a **real risk of significant harm** to individuals:

| Timeframe | Action |
|---|---|
| **Immediately** | Contain the breach. Preserve evidence — do not delete logs, rotate secrets, or wipe systems without preserving a forensic copy. Identify the scope: what data, how many individuals, which practices affected. |
| **As soon as feasible (target: within 72 hours)** | Notify the **Office of the Privacy Commissioner of Canada (OPC)**. Report via the OPC's online breach report form. Include: nature of the breach, estimated number of individuals affected, steps taken to contain it. |
| **As soon as feasible after OPC notification** | Notify **affected individuals directly** if there is a real risk of significant harm. Use the contact information on file (email or phone). Do not delay notification to affected individuals while investigating. |
| **Within 24 months of the breach** | Maintain a **breach record** documenting: date of breach, nature of breach, steps taken, individuals affected. This record must be available to the OPC on request. |

### What counts as "real risk of significant harm"

Significant harm includes bodily harm, humiliation, damage to reputation, loss of employment, financial loss, identity theft, negative effects on a credit record, and damage to relationships.

For dental patient data, the following likely trigger the real-risk threshold:
- Exposure of clinical notes, diagnoses, or treatment history
- Exposure of SIN, health card numbers, or insurance policy numbers
- Exposure of contact information combined with health status
- Exposure of financial or billing information

### Internal escalation contacts

Maintain an internal access register (separate document) with named contacts for:
- Privacy Officer / DPO
- Legal counsel
- Practice owner / CEO
- GCP Project Owner

---

## Related Documents

- [SECRETS.md](SECRETS.md) — Secret inventory and normal rotation procedures
- [RETENTION.md](RETENTION.md) — Log and data retention policy
- [SECURITY.md](SECURITY.md) — Security controls overview
