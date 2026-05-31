# Data Processing Agreement Register
**Last updated:** 2026-05-31
**Jurisdiction:** Canada — PIPEDA

---

## Status Key

- ✅ Executed — DPA in place
- ⏳ In progress — DPA under review
- ❌ Not started — required before live clinic data

---

## Third-Party DPA Status

| Service | Purpose | PHI Sent | DPA Status | Executed Date | Notes |
|---|---|---|---|---|---|
| MongoDB Atlas | Primary data storage | Full patient records | ✅ Executed | — | Atlas DPA covers all tiers |
| Stripe | Billing only | Billing contact only | ✅ Executed | — | No clinical PHI |
| OpenAI | AI receptionist reasoning | Redacted prompts only | ❌ Not started | — | Required before live clinic |
| Anthropic (Claude) | AI reasoning fallback | Redacted prompts only | ❌ Not started | — | Required before live clinic |
| Groq | Fast inference | Redacted prompts only | ❌ Not started | — | Required before live clinic |
| Retell | Voice call handling | Caller audio + transcripts | ❌ Not started | — | Highest risk — audio is PHI |
| Google Cloud | Compute + Secret Manager | Encrypted secrets only | ✅ Executed | — | GCP DPA covers Cloud Run |

---

## Action Items Before First Live Clinic

1. **Retell** — Execute BAA or DPA covering call audio and transcripts (highest priority — audio is PHI)
2. **OpenAI** — Execute Data Processing Addendum (platform.openai.com/docs/privacy)
3. **Anthropic** — Confirm API DPA covers dental PHI use case
4. **Groq** — Confirm DPA covers inference API usage with redacted health data

---

## Data Residency Confirmation

| Component | Current Region | Target (Canadian) | Status |
|---|---|---|---|
| Cloud Run (primary) | us-west1 (Oregon) | northamerica-west2 (Calgary) | ⏳ Migration planned |
| Cloud Run (east) | — | northamerica-northeast1 (Montreal) | ❌ Not deployed |
| MongoDB Atlas | TBC | Canada West + Canada East clusters | ⏳ Confirm Atlas cluster region |

---

## Notes

- Data residency migration must complete before onboarding any live clinic
- DPAs must be executed before live patient data touches third-party APIs
- Maintain this register — auditors will ask for it
- See [DATA_FLOW.md](DATA_FLOW.md) for details on what PHI is sent to each service
- See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) for breach notification obligations under PIPEDA
