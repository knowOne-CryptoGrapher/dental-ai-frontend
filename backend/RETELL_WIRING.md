# Retell AI — Wiring Guide

**Backend service:** `dental-ai-backend` (Cloud Run, us-west1)  
**Last updated:** 2026-07-10

---

## 1. Find Your Base URL

Run once to get the live service URL:

```powershell
gcloud run services describe dental-ai-backend `
    --region us-west1 --project dental-ai-backend `
    --format "value(status.url)"
```

Returns something like `https://dental-ai-backend-abc12345-uw.a.run.app`.  
Replace `$BASE_URL` with that value everywhere below.

---

## 2. Webhook URL

**Where:** Retell Dashboard → Settings → Webhooks  
**Value:**
```
$BASE_URL/api/retell/webhook
```

Receives all Retell call lifecycle events (`call_started`, `call_ended`, `call_analyzed`,
`call_error`). Strict HMAC-SHA256 signature verification — any failure returns 401
immediately. The `x-retell-signature` header is set automatically by Retell.

---

## 3. Custom LLM URL

**Where:** Retell Dashboard → Agents → [your agent] → LLM → Custom LLM  
**Value:**
```
$BASE_URL/api/llm/chat/completions
```

OpenAI-compatible streaming endpoint (`text/event-stream`). Routes between
GPT-4o-mini and Groq Llama 3.3 based on message complexity. This endpoint is
intentionally unauthenticated — Retell does not sign LLM requests.

---

## 4. Function Nodes

Add each function in Retell Dashboard → Agents → [your agent] → Functions.

> **Phone number auto-injection:** The backend reads the real caller number from
> Retell's `call.from_number` and injects it as `phone_number` / `patient_phone`
> on every request, overriding whatever the LLM passed. The agent should never
> ask the caller for their phone number.

> **`practice_id` global variable:** Every function requires `practice_id`.
> Configure it once in Retell's agent "Dynamic Variables" panel and reference
> it as `{{practice_id}}` in the agent prompt. The LLM will include it
> automatically in each function call.

---

### 4.1 `check_provider_availability`

**URL:** `POST $BASE_URL/api/retell/check-provider-availability`

```json
{
  "name": "check_provider_availability",
  "description": "Check whether a specific provider is available on a given date and optional time. Returns available time slots. Rejects past dates and returns a suggested corrected future date so you can confirm with the caller without guessing.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID (injected from global variable)."
      },
      "provider_name": {
        "type": "string",
        "description": "Provider last name or full name, e.g. 'Smith' or 'Dr. Sarah Smith'."
      },
      "date": {
        "type": "string",
        "description": "Date to check in YYYY-MM-DD format. Defaults to today if omitted."
      },
      "time": {
        "type": "string",
        "description": "Optional specific time in HH:MM 24-hour format, e.g. '14:00'."
      }
    },
    "required": ["practice_id", "provider_name"]
  }
}
```

---

### 4.2 `list_providers`

**URL:** `POST $BASE_URL/api/retell/list-providers`

```json
{
  "name": "list_providers",
  "description": "List all active providers at the clinic. Optionally filter by specialty. Use when the caller asks 'who are your dentists?' or 'do you have a hygienist?'",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "specialty": {
        "type": "string",
        "description": "Optional specialty filter, e.g. 'General Dentist', 'Hygienist', 'Orthodontist'."
      }
    },
    "required": ["practice_id"]
  }
}
```

---

### 4.3 `lookup_patient`

**URL:** `POST $BASE_URL/api/retell/lookup-patient`

```json
{
  "name": "lookup_patient",
  "description": "Look up an existing patient by phone number. Returns patient name, appointment history, preferred provider, and a personalised greeting. Call this at the start of every inbound call to determine if the caller is a returning patient.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "phone_number": {
        "type": "string",
        "description": "Caller's phone number. Auto-injected from call.from_number — do not ask the caller."
      }
    },
    "required": ["practice_id", "phone_number"]
  }
}
```

---

### 4.4 `register_patient`

**URL:** `POST $BASE_URL/api/retell/register-patient`

```json
{
  "name": "register_patient",
  "description": "Create a new patient profile WITHOUT booking an appointment. Idempotent — if the caller already exists in the system, returns their existing record. Use when a new caller wants to register but is not ready to book.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "patient_name": {
        "type": "string",
        "description": "Patient's full name as spoken, e.g. 'Jane Doe'."
      },
      "patient_email": {
        "type": "string",
        "description": "Patient's email address (optional)."
      },
      "date_of_birth": {
        "type": "string",
        "description": "Patient's date of birth in YYYY-MM-DD format (optional)."
      }
    },
    "required": ["practice_id", "patient_name"]
  }
}
```

> `patient_phone` is auto-injected from `call.from_number`.

---

### 4.5 `book_appointment`

**URL:** `POST $BASE_URL/api/retell/book-appointment`

```json
{
  "name": "book_appointment",
  "description": "Book a dental appointment for the caller. Creates a patient record if one does not already exist. Rejects past dates and returns a corrected future date suggestion — always confirm date and time with the caller before calling this function.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "patient_name": {
        "type": "string",
        "description": "Patient's full name."
      },
      "patient_email": {
        "type": "string",
        "description": "Patient's email address (optional, used for confirmation emails)."
      },
      "date": {
        "type": "string",
        "description": "Appointment date in YYYY-MM-DD format. Must be a future date."
      },
      "time": {
        "type": "string",
        "description": "Appointment time in HH:MM 24-hour format, e.g. '14:00'."
      },
      "reason": {
        "type": "string",
        "description": "Reason for the visit, e.g. 'Cleaning', 'Checkup', 'Toothache', 'Emergency'."
      },
      "provider_name": {
        "type": "string",
        "description": "Preferred provider name (optional). Pass last name or full name."
      },
      "is_emergency": {
        "type": "boolean",
        "description": "Set true only if the caller explicitly described a dental emergency."
      }
    },
    "required": ["practice_id", "patient_name", "date", "time"]
  }
}
```

> `patient_phone` is auto-injected from `call.from_number`.

---

### 4.6 `get_patient_appointments`

**URL:** `POST $BASE_URL/api/retell/get-patient-appointments`

```json
{
  "name": "get_patient_appointments",
  "description": "Retrieve the caller's upcoming scheduled appointments. Use when the caller asks 'when is my next appointment?' or 'do I have anything booked?'",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "phone_number": {
        "type": "string",
        "description": "Caller's phone number. Auto-injected from call.from_number."
      }
    },
    "required": ["practice_id", "phone_number"]
  }
}
```

---

### 4.7 `cancel_appointment`

**URL:** `POST $BASE_URL/api/retell/cancel-appointment`

```json
{
  "name": "cancel_appointment",
  "description": "Cancel a specific appointment by ID. Always call get_patient_appointments first to get the appointment ID, then confirm with the caller before calling this function.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "appointment_id": {
        "type": "string",
        "description": "UUID of the appointment to cancel (obtained from get_patient_appointments)."
      },
      "phone_number": {
        "type": "string",
        "description": "Caller's phone number for identity verification. Auto-injected from call.from_number."
      }
    },
    "required": ["practice_id", "appointment_id", "phone_number"]
  }
}
```

---

### 4.8 `query_knowledge_base`

**URL:** `POST $BASE_URL/api/knowledge/query`

**Required custom header (set in Retell function config):**
```
x-retell-api-key: <value of RETELL_API_KEY>
```

```json
{
  "name": "query_knowledge_base",
  "description": "Search the clinic's knowledge base for answers to patient questions about services, pricing, insurance, hours, parking, accessibility, etc. Always call this before saying you don't know something — the answer may be in the knowledge base. If confidence is 'none', tell the caller you'll have the team follow up.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "question": {
        "type": "string",
        "description": "The patient's question verbatim or close paraphrase, e.g. 'Do you accept Blue Cross dental insurance?'"
      }
    },
    "required": ["practice_id", "question"]
  }
}
```

Response: `{ "answer": "...", "source": "document title", "confidence": "high"|"low"|"none" }`

---

### 4.9 `ingest_call_summary` (end-of-call)

**URL:** `POST $BASE_URL/api/retell/call-summary`

**Required custom header (set in Retell function config):**
```
x-retell-secret: <value of RETELL_WEBHOOK_SECRET>
```

Configure this as the **last function the agent calls on every call**, just before
saying goodbye. It records the outcome and creates follow-up tasks for the practice team.

```json
{
  "name": "ingest_call_summary",
  "description": "ALWAYS call this at the very end of every conversation, just before saying goodbye. Records the call outcome so the practice team can review it and act on follow-ups.",
  "parameters": {
    "type": "object",
    "properties": {
      "practice_id": {
        "type": "string",
        "description": "The clinic's practice ID."
      },
      "call_id": {
        "type": "string",
        "description": "The Retell call ID for this call. Available as {{call_id}} in the agent context."
      },
      "reason": {
        "type": "string",
        "description": "One sentence describing why the caller called, e.g. 'Patient called to book a cleaning appointment'."
      },
      "outcome": {
        "type": "string",
        "enum": ["appointment_booked", "appointment_cancelled", "info_provided", "transferred", "voicemail", "abandoned", "other"],
        "description": "The result of the call."
      },
      "follow_up_needed": {
        "type": "boolean",
        "description": "True if the practice team needs to follow up — e.g. unresolved billing question, failed transfer, or emergency escalation."
      },
      "tags": {
        "type": "array",
        "items": { "type": "string" },
        "description": "Optional short labels, e.g. ['new_patient', 'insurance', 'emergency']."
      },
      "transcript": {
        "type": "string",
        "description": "Full call transcript (optional)."
      }
    },
    "required": ["practice_id", "call_id", "reason", "outcome", "follow_up_needed"]
  }
}
```

---

## 5. Post-Call Webhook (Alternative to §4.9)

Retell supports a dashboard-configured post-call webhook as an alternative to the
end-of-call function node. You can use either or both — the endpoint is idempotent
(uses `upsert=True`, so a second write updates the same `call_logs` document).

**Where:** Retell Dashboard → Agents → [your agent] → Post-Call Webhook  
**URL:** `POST $BASE_URL/api/retell/call-summary`  
**Custom Header:** `x-retell-secret: <value of RETELL_WEBHOOK_SECRET>`

In the Retell payload template editor, map these fields:

| Retell variable | Body field |
|---|---|
| `{{practice_id}}` | `practice_id` |
| `{{call_id}}` | `call_id` |
| *(from agent state)* | `reason` |
| *(from agent state)* | `outcome` |
| *(from agent state)* | `follow_up_needed` |

---

## 6. Environment Variables Checklist

| Variable | Purpose | Where to find the value |
|---|---|---|
| `RETELL_API_KEY` | Authenticates outbound Retell SDK calls; also used as the `x-retell-api-key` header value for `/api/knowledge/query` | Retell Dashboard → API Keys |
| `RETELL_WEBHOOK_SECRET` | HMAC-SHA256 signing key for verifying inbound lifecycle webhook signatures; also used as `x-retell-secret` for `/api/retell/call-summary` | Retell Dashboard → Settings → Webhooks → Signing Secret |

Both are provisioned in GCP Secret Manager via `$SECRET_VARS` in `deploy_backend.ps1`
and mounted into Cloud Run as `secretKeyRef` entries. Do **not** add them as plain
string values in `service.yaml`.

**Verify the secrets are mounted (not plain values) in the running revision:**

```powershell
gcloud run services describe dental-ai-backend `
    --region us-west1 --project dental-ai-backend `
    --format "yaml(spec.template.spec.containers[0].env)"
```

Both should appear under `valueFrom.secretKeyRef`, not `value`.

---

## 7. Testing Instructions

### 7.1 Unit tests (no network required)

```powershell
cd C:\Dev\dental-ai-frontend\backend
$env:MONGODB_URI = (Select-String -Path .env -Pattern '^MONGODB_URI=').Line -replace '^MONGODB_URI=',''
.\venv\Scripts\python.exe -m pytest tests/test_retell_v2.py -v
```

Expected: 10 passed, 0 failed.

### 7.2 Smoke-test the webhook endpoint

Start locally:

```bash
cd backend && uvicorn server:app --reload --port 8000
```

Send a test `call_started` event (generate a valid HMAC or temporarily set
`RETELL_WEBHOOK_SECRET=""` to bypass — never in production):

```bash
curl -s -X POST http://localhost:8000/api/retell/webhook \
  -H "Content-Type: application/json" \
  -H "x-retell-signature: t=<timestamp_ms>,v1=<hmac>" \
  -d '{
    "event": "call_started",
    "call": {
      "call_id": "test-001",
      "from_number": "+16041234567",
      "to_number": "+16045559999",
      "agent_id": "agent-001",
      "start_timestamp": <timestamp_ms>,
      "metadata": { "practice_id": "<your-practice-id>" }
    }
  }'
```

Expected: `{"status": "ok"}`

### 7.3 Test function nodes end-to-end via Retell Dashboard

1. Retell Dashboard → Agents → [your agent] → **Test** tab → Start a test call.
2. Speak each trigger phrase below. The test panel shows the function call payload and backend response in real time.

| Function | Trigger phrase |
|---|---|
| `lookup_patient` | *(auto at call start — observe the greeting)* |
| `list_providers` | "Who are your dentists?" |
| `check_provider_availability` | "Is Dr. Lee available next Tuesday?" |
| `book_appointment` | "I'd like to book a cleaning for next Friday at 2 PM." |
| `get_patient_appointments` | "When is my next appointment?" |
| `cancel_appointment` | "I need to cancel my appointment." |
| `register_patient` | "I'm a new patient and I'd like to register." |
| `query_knowledge_base` | "Do you accept Blue Cross insurance?" |
| `ingest_call_summary` | *(auto at call end — confirm `{"success": true}`)* |

### 7.4 Verify the post-call DB write

After a test call ends, check MongoDB Atlas → Collections → `call_logs`:

```js
db.call_logs.find({ call_id: "<your-test-call-id>" }).pretty()
```

A complete call should have `status: "completed"`, a non-empty `transcript`,
and `call_summary` populated. If `follow_up_needed` was true, a matching
document should exist in `pending_actions` with `status: "pending"`.

---

## 8. Migration Notes

### What was removed and why

| File | Reason |
|---|---|
| `backend/routers/retell_router.py` | Duplicate of `retell_api_router.py` — defined a second `router` and `logger` with identical names, causing silent conflicts. Was registered alongside `retell_api_router` on overlapping routes. Dead code with no unique logic. |
| `backend/routers/retell_webhook_router.py` | Legacy webhook handler with **soft signature verification**: on a bad HMAC it logged a warning and continued processing the payload anyway. Also ran inline auto-analysis (appointment extraction, patient lookup) inside the webhook handler, coupling event ingestion to business logic in a way that could silently create incorrect records. Replaced by `retell_webhook_router_v2`. |
| `backend/retell.py` | Original v1 single-tenant design. Resolved `practice_id` by selecting the first practice returned from the database — unsafe and wrong in any multi-clinic deployment. |
| `backend/retell_stub.py` | Development stub that exported `verify()` → always `True`. Dangerous if accidentally imported over the real SDK in production. Zero imports confirmed before deletion. |

### What replaced them

| New file | Role |
|---|---|
| `backend/routers/retell_webhook_router_v2.py` | Lifecycle event receiver. Strict HMAC-SHA256 — raises 401 immediately on failure, never log-and-continue. Passive recording only: no auto-patient creation, no auto-appointment creation, no emergency side-effects. Practice ID resolves as: `metadata.practice_id` → agent_id DB lookup → `None` (never falls back to first-in-DB). |
| `backend/routers/retell_context_router.py` | Agent bootstrap and knowledge endpoints. `GET /api/practice/me` returns full practice config (hours, providers, appointment types, emergency rules, branding). `POST /api/knowledge/query` provides keyword-scored knowledge base search. `POST /api/retell/call-summary` ingests end-of-call summaries with `upsert=True` idempotency. |

### Registration changes in `server.py`

Removed:
```python
from routers.retell_router import router as retell_router
from routers.retell_webhook_router import router as retell_webhook_router
app.include_router(retell_router)
app.include_router(retell_webhook_router)
```

Added:
```python
from routers.retell_webhook_router_v2 import router as retell_webhook_router_v2
from routers.retell_context_router import router as retell_context_router
app.include_router(retell_webhook_router_v2)
app.include_router(retell_context_router)
```

`retell_api_router` (the 7 function-call endpoints) was unchanged throughout.

### Known post-deploy backlog

**Cross-practice JWT scoping on `/api/knowledge/query`:**  
The JWT path currently accepts any valid Bearer token without checking whether
`jwt.practice_id` matches `body.practice_id`. A staff member from practice A could
query documents from practice B by passing a different `practice_id` in the body.
Fix: validate `jwt.practice_id == body.practice_id` before querying
`knowledge_documents`. Lower priority because knowledge base content is not PHI
and the Retell agent path authenticates via API key rather than JWT.
