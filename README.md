# Front Desk Dental AI

AI-powered dental receptionist platform for Canadian dental practices. Handles inbound calls, books appointments, manages patient records, and processes insurance claims.

**Live at:** [frontdeskdentalai.com](https://frontdeskdentalai.com)

---

## Architecture

```
Caller → Retell AI (voice/STT/TTS)
       → Google Cloud Run northamerica-northeast1 (FastAPI backend)
       → MongoDB Atlas (patient data — single cluster today; Canadian-region
         split into ca-west/ca-east is planned, not yet executed, see
         docs/DATA_FLOW.md)
       → Groq llama-3.3-70b-versatile (default LLM inference)
       → Anthropic claude-haiku-4-5-20251001 (escalation/emergency)

Frontend → Cloudflare Pages (React 19 + CRACO)
Backend  → Google Cloud Run (northamerica-northeast1, Montreal)
DNS      → Cloudflare → Global HTTPS Load Balancer (34.120.47.218)
Email    → Amazon SES v2 (ca-central-1, production)
Billing  → Stripe
```

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, CRACO, Cloudflare Pages |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Database | MongoDB Atlas (`dental_ai`) |
| Voice AI | Retell AI — speech-to-text, TTS, function calling |
| LLM Default | Groq llama-3.3-70b-versatile |
| LLM Escalation | Anthropic claude-haiku-4-5-20251001 |
| Email | Amazon SES v2, ca-central-1 |
| Billing | Stripe |
| Infrastructure | Google Cloud Run, Global HTTPS Load Balancer |
| Secrets | GCP Secret Manager |
| CI/CD | Cloud Build (backend), Cloudflare Pages (frontend) |

---

## Repository Structure

```
dental-ai-frontend/
├── frontend/                  # React 19 frontend
│   └── src/
│       ├── pages/             # Dashboard, Appointments, CallLogs, Patients, Billing, Settings
│       ├── components/        # Shared UI components
│       └── config/            # API config, legal version constants
├── backend/                   # FastAPI backend
│   ├── routers/               # API route handlers
│   ├── services/              # Email, LLM, external services
│   ├── utils/                 # Phone normalization, scheduling, security
│   ├── llm/                   # LLM router, providers (Groq, Anthropic, OpenAI)
│   ├── cdn/                   # CDAnet/ITRANS claims scaffold (Phase 2, no README yet)
│   ├── templates/email/       # SES email templates (patient + admin)
│   ├── tests/                 # Test suites
│   ├── scripts/               # One-time migration scripts (not committed after use)
│   ├── service.yaml           # Cloud Run service definition
│   ├── HANDOFF.md             # Living session handoff document
│   └── RETELL_WIRING.md       # Retell dashboard setup guide
├── deploy_backend.ps1         # Backend deploy script (provisions secrets + deploys)
└── README.md                  # This file
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- PowerShell (for deploy script)
- Google Cloud CLI (`gcloud`)

### Backend setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt --break-system-packages

# Copy and fill in environment variables
cp .env.example .env
# Edit .env with your keys

# Run locally
uvicorn server:app --reload --port 8000
```

### Frontend setup

```bash
cd frontend
npm install
npm start
```

### Environment variables

All secrets are managed via GCP Secret Manager in production. For local development, copy `.env.example` to `.env` and fill in:

```
MONGODB_URI=
JWT_SECRET_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
RETELL_API_KEY=
RETELL_WEBHOOK_SECRET=
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_BASIC=
STRIPE_PRICE_PROFESSIONAL=
STRIPE_PRICE_ENTERPRISE=
STRIPE_PRICE_ELITE=
SES_ACCESS_KEY_ID=
SES_SECRET_ACCESS_KEY=
SES_REGION=ca-central-1
SES_FROM_EMAIL=noreply@frontdeskdentalai.com
SES_FROM_NAME=Front Desk Dental AI
SES_CONFIGURATION_SET=dental-ai-email-events
INTERNAL_API_KEY=
SALES_NOTIFY_EMAIL=
PUBLIC_BACKEND_URL=https://api.frontdeskdentalai.com
```

---

## Deployment

### Backend

```powershell
cd C:\Dev\dental-ai-frontend
.\deploy_backend.ps1
```

The deploy script:
1. Reads all secrets from `.env`
2. Provisions new secrets to GCP Secret Manager
3. Patches `service.yaml` with the current image tag
4. Deploys to Cloud Run `northamerica-northeast1` via `gcloud run services replace`
5. Routes 100% traffic to the new revision

Public traffic reaches the backend via a Global HTTPS Load Balancer (static IP `34.120.47.218`) in front of the Cloud Run service, not a direct Cloud Run domain mapping — see `backend/HANDOFF.md` for the migration history.

**Never commit `.env` — it is git-ignored.**

### Frontend

Push to `unlocked-main` — Cloudflare Pages auto-deploys.

---

## Key Endpoints

### Public
- `GET /health` — health check
- `POST /api/auth/login` — authentication
- `POST /api/auth/signup` — self-serve registration (Basic plan)
- `POST /api/sales/contact` — contact sales (Enterprise/Elite)
- `POST /api/sales/founding-clinic` — founding clinic application
- `GET /api/sales/founding-clinic-count` — spots remaining

### Authenticated (JWT)
- `GET /api/call-logs` — practice call logs
- `GET /api/appointments` — practice appointments
- `GET /api/patients` — practice patients
- `GET /api/billing/features` — plan features and billing status
- `GET /api/admin/notifications/settings` — notification preferences

### Retell AI (API key auth)
- `POST /api/retell/webhook` — Retell webhook (HMAC verified)
- `POST /api/retell/practice-context` — agent practice context + current date
- `POST /api/retell/lookup-patient` — patient lookup by phone
- `POST /api/retell/book-appointment` — appointment booking
- `POST /api/retell/check-provider-availability` — availability check
- `POST /api/retell/list-providers` — provider list
- `POST /api/retell/get-patient-appointments` — patient appointments
- `POST /api/retell/cancel-appointment` — appointment cancellation
- `POST /api/retell/register-patient` — patient registration
- `POST /api/knowledge/query` — knowledge base query
- `POST /api/retell/call-summary` — post-call summary ingestion

### Superadmin (super_admin role)
- `GET /api/superadmin/dashboard` — platform stats
- `GET /api/superadmin/practices` — all practices
- `POST /api/superadmin/practices` — create practice
- `GET /api/superadmin/leads` — sales lead queue
- `POST /api/superadmin/leads/{id}/approve` — approve lead
- `POST /api/superadmin/leads/{id}/deny` — deny lead
- `GET /api/superadmin/retell/{practice_id}` — Retell provisioning info

---

## Plan Tiers

| Plan | Price | Self-serve | Features |
|---|---|---|---|
| Basic | $499/mo | ✅ | Core receptionist, appointments, call logs |
| Professional | $699/mo | ✅ | + Analytics, insurance verification |
| Enterprise | $999/mo | Contact sales | + Knowledge base, custom routing |
| Elite | $1,499/mo | Contact sales | + BAA, dedicated support |

**Founding Clinic rate:** $299/mo locked for life — BC clinics only, 10 spots.

Plan gates return **402 Payment Required** for blocked features.
`ENFORCE_PLAN_GATES=true` in Cloud Run.

---

## Retell Integration

See `backend/RETELL_WIRING.md` for the full Retell dashboard setup guide.

**Agent:** `agent_3420090c2d922714273ae4ad39` (test practice)
**Webhook:** `https://api.frontdeskdentalai.com/api/retell/webhook`
**10 function nodes** — all documented in RETELL_WIRING.md

**Payload: args only OFF for:** `lookup_patient`, `book_appointment`, `get_patient_appointments`, `cancel_appointment`
**Payload: args only ON for:** all other functions

---

## LLM Routing

```
Default:    Groq llama-3.3-70b-versatile ($0.59/1M tokens)
Escalation: Anthropic claude-haiku-4-5-20251001
```

Routing rules in `backend/llm/router.py`. Emergency detection in `backend/utils/retell_security.py`.

---

## Email

Amazon SES v2, `ca-central-1`, production access confirmed.

- **From:** `noreply@frontdeskdentalai.com`
- **Configuration set:** `dental-ai-email-events`
- **Bounce/complaint handling:** SNS topics → `ses_webhook_router.py` → `email_suppression_list`
- **Templates:** `backend/templates/email/` (patient) and `backend/templates/email/admin/` (admin)

---

## Security

- JWT authentication on all protected endpoints
- HMAC-SHA256 webhook verification (Retell)
- Rate limiting: `/signup` and `/register` at 10/hour
- MongoDB compound unique index on `(practice_id, normalized_phone)`
- Phone normalization: E.164 via `backend/utils/phone.py`
- Plan gates enforced server-side (402 for blocked features)
- All secrets in GCP Secret Manager — never in git
- `RequestValidationError` handler logs all 422s with field detail

---

## Testing

```powershell
cd backend

# Set env
$env:MONGODB_URI = (Select-String -Path .env -Pattern '^MONGODB_URI=').Line -replace '^MONGODB_URI=',''
$env:TEST_API_URL = "https://api.frontdeskdentalai.com"

# Run all tests
.\venv\Scripts\python.exe -m pytest tests/ -v --tb=short

# Key test files
.\venv\Scripts\python.exe -m pytest tests/test_retell_v2.py -v           # Retell webhook (10 tests)
.\venv\Scripts\python.exe -m pytest tests/test_patient_deduplication.py -v # Phone normalization (16 tests)
.\venv\Scripts\python.exe -m pytest tests/test_admin_email.py -v           # Admin email (6 tests)
.\venv\Scripts\python.exe -m pytest tests/test_plan_gates_basic.py tests/test_plan_gates_professional.py tests/test_registration_flow_enterprise.py -v  # Plan gates (34 tests)

# Load/stress test (requires admin@dentalai.test in DB)
.\venv\Scripts\python.exe scripts/stress_test.py --base-url https://api.frontdeskdentalai.com --scenarios D --concurrency 25 --duration 60 --cleanup

# Retell simulation harness
.\venv\Scripts\python.exe tests/retell_sim/scenario_runner.py --practice-id practice-test-001 --agent-id agent_3420090c2d922714273ae4ad39 --cleanup
```

---

## Compliance

- **PIPEDA:** compute now in `northamerica-northeast1` (Montreal). MongoDB Atlas is still a single cluster with its Canadian-region split (`ca-west`/`ca-east`) planned but not yet executed — see `docs/DATA_FLOW.md` and `docs/PHIPA_PIPEDA_CHECKLIST.md` (draft) for current gaps.
- **Privacy Policy:** v1.1 — includes call recording disclosure, AI processor list
- **Terms of Service:** v1.2 — AI technology disclosure (Groq, OpenAI, Anthropic, Retell)
- **PHI redaction:** patient-identifying info stripped before any LLM inference call
- **DPAs:** Executed — MongoDB Atlas, Stripe, Google Cloud. **Not started** — OpenAI, Anthropic, Groq, Retell (Retell is highest priority: call audio is PHI). See `docs/DPA_REGISTER.md` for the current register; required before any live (non-test) clinic data.
- **PHIPA (Ontario):** not addressed — this platform is scoped BC-only today. A separate PHIPA review is required before any Ontario expansion.
- **Incorporation:** BC Provincial corporation — *[legal entity name not on file in this repo; fill in before external use]*

---

## Phase 2 — CDAnet/ITRANS Claims (Pending)

Insurance claims submission scaffold is built at `backend/cdn/` (`cdanet/`, `claims/`, `itrans/`). Full implementation is blocked on:
1. TELUS Health ITRANS vendor credentials
2. CDA Software Vendor Agreement

No dedicated README exists for this module yet.

---

## Superadmin

Access at `frontdeskdentalai.com/login` with `super_admin` role credentials.

- `/admin` — Platform dashboard (practices, calls, patients, revenue)
- `/admin/leads` — Sales lead approval queue
- `/admin/practices` — Manage all practices
- `/admin/retell` — Retell provisioning guide
- `/admin/llm` — LLM routing configuration

---

## Session Continuity

See `backend/HANDOFF.md` for the living session handoff document. Read this at the start of every Claude Code session before making any changes.
