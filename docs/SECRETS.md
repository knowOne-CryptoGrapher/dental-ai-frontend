# Secrets Inventory — Dental AI Backend

All secrets are stored in **GCP Secret Manager** under project `dental-ai-backend`.
The deploy script (`deploy_backend.ps1`) creates or updates them from `backend/.env`
on every deploy.

---

## Secret Inventory

| Secret Name | Env Var | Used By | Rotation |
|---|---|---|---|
| `MONGODB_URI` | `MONGODB_URI` | Motor / PyMongo | Rotate via Atlas → update secret version |
| `JWT_SECRET_KEY` | `JWT_SECRET_KEY` | `auth.py` (HS256 signing) | Rotate → all active sessions invalidated |
| `OPENAI_API_KEY` | `OPENAI_API_KEY` | `ai_service.py`, LLM router | OpenAI dashboard → revoke old key |
| `ANTHROPIC_API_KEY` | `ANTHROPIC_API_KEY` | LLM router (escalation) | Anthropic console |
| `GROQ_API_KEY` | `GROQ_API_KEY` | `ai_service.py` (fast inference) | Groq console |
| `RETELL_API_KEY` | `RETELL_API_KEY` | Retell webhook verification, provisioning | Retell dashboard |
| `STRIPE_SECRET_KEY` | `STRIPE_SECRET_KEY` | `billing_router.py` | Stripe dashboard → restricted keys |
| `STRIPE_WEBHOOK_SECRET` | `STRIPE_WEBHOOK_SECRET` | `stripe_webhook_router.py` | Stripe dashboard → webhook endpoint |

---

## Non-Secret Configuration (plain env vars in service.yaml)

| Env Var | Value | Notes |
|---|---|---|
| `DATABASE_NAME` | `dental_ai` | MongoDB database name |
| `LOG_LEVEL` | `INFO` | Set to `DEBUG` temporarily for troubleshooting |
| `CORS_ORIGINS` | comma-separated URLs | Production frontend origins |
| `LLM_DEFAULT_PROVIDER` | `openai` | |
| `LLM_DEFAULT_MODEL` | `gpt-4o-mini` | |
| `LLM_ESCALATION_PROVIDER` | `anthropic` | |
| `LLM_ESCALATION_MODEL` | `claude-3-7-sonnet` | |
| `LLM_RULES_PATH` | `llm/llm_rules.json` | Relative to `/app` in container |
| `LLM_PRICING_PATH` | `llm/llm_pricing.json` | |
| `OPENAI_TEXT_MODEL` | `gpt-4o-mini` | |
| `OPENAI_JSON_MODEL` | `gpt-4o-mini` | |
| `GROQ_TEXT_MODEL` | `llama3-70b-8192` | |
| `GROQ_JSON_MODEL` | `llama3-70b-8192` | |
| `STRIPE_PRICE_*` | price_… IDs | Not secret — these are public plan IDs |

---

## How to Create / Rotate a Secret

### Create (first time)

Run `deploy_backend.ps1` — it enables the Secret Manager API, reads `backend/.env`, and
creates every secret in the inventory above if it does not exist.

Manually:
```powershell
echo -n "SECRET_VALUE" | gcloud secrets create MY_SECRET `
    --project dental-ai-backend `
    --data-file=-
```

### Rotate (add a new version)

```powershell
echo -n "NEW_VALUE" | gcloud secrets versions add MY_SECRET `
    --project dental-ai-backend `
    --data-file=-
```

`service.yaml` references `key: latest`, so Cloud Run picks up the new version on next
deployment. To force an immediate rollout without a new build:

```powershell
gcloud run services replace backend/service.yaml `
    --platform managed --region us-west1 --project dental-ai-backend
```

### JWT_SECRET_KEY rotation note

Rotating `JWT_SECRET_KEY` invalidates **all active user sessions** immediately — every
logged-in user will be logged out on their next request. Schedule during low-traffic
hours and notify users in advance if possible.

---

## IAM

The Cloud Run service account (`244697312574-compute@developer.gserviceaccount.com`)
has `roles/secretmanager.secretAccessor` granted on each secret individually
(least-privilege). `deploy_backend.ps1` handles this grant automatically.

To verify:
```powershell
gcloud secrets get-iam-policy MONGODB_URI --project dental-ai-backend
```

---

## What Is NOT in Secret Manager

- Stripe Price IDs (`STRIPE_PRICE_*`) — these are public plan identifiers, not credentials.
- `DATABASE_NAME`, `LOG_LEVEL`, model names — non-sensitive configuration.
- `.env` file — **never committed to git** (listed in `.gitignore` and `.dockerignore`).
