# Data Processing Agreement Register
**Last updated:** 2026-09-11
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
| Anthropic (Claude) | AI reasoning fallback | Redacted prompts only | ✅ Resolved — no signature needed | Sept 2026 | Anthropic confirmed their DPA is auto-incorporated into their Commercial Terms of Service; no separate execution required. Supporting compliance documentation (SOC 2/3, ISO 27001/42001, HIPAA Type 1, security whitepapers, vendor questionnaires) obtained via Trust Center under NDA — see `docs/compliance/anthropic/` (gitignored). |
| Groq | Fast inference | Redacted prompts only | ⏳ Requested — awaiting response | Requested Sept 2026 | Request letter sent; DPA not yet confirmed |
| Retell | Voice call handling | Caller audio + transcripts | ⏳ Requested — awaiting response | Requested Sept 2026 | Request letter sent; still highest priority — audio is PHI |
| Google Cloud | Compute + Secret Manager | Encrypted secrets only | ✅ Executed | — | GCP DPA covers Cloud Run |

---

## Action Items Before First Live Clinic

1. **Retell** — Follow up on request letter (sent Sept 2026); execute BAA or DPA covering call audio and transcripts (highest priority — audio is PHI)
2. **OpenAI** — Execute Data Processing Addendum (platform.openai.com/docs/privacy)
3. **Groq** — Follow up on request letter (sent Sept 2026); confirm DPA covers inference API usage with redacted health data

~~**Anthropic** — Confirm API DPA covers dental PHI use case~~ **DONE (Sept 2026)** — confirmed auto-incorporated into their Commercial Terms of Service, no action needed.

---

## Data Residency Confirmation

| Component | Current Region | Status |
|---|---|---|
| Cloud Run | northamerica-northeast1 (Montreal), GCP | ✅ Live since 2026-09-09 — confirmed via `gcloud run services describe` and direct `/health/ready` check |
| MongoDB Atlas | us-west1 (Oregon), GCP — confirmed `region: WESTERN_US`, `availabilityZone: us-west1-a/b/c` via direct `replSetGetConfig()`/`hello()` query against the live cluster | ⏳ Region migration to `northamerica-northeast1` attempted via Atlas's native "Edit Configuration" region-edit feature, but **not yet confirmed live** — as of the last direct verification (2026-09-11) the cluster is still reporting its original `us-west1` region. Do not mark this done until re-verified post-migration. |

*(Note: a previous version of this table listed `northamerica-west2 (Calgary)` as the Cloud Run target — that region does not exist on GCP; GCP's only Canadian regions are `northamerica-northeast1` (Montreal) and `northamerica-northeast2` (Toronto). Removed entirely, not just relabeled.)*

---

## Notes

- Data residency migration must complete before onboarding any live clinic
- DPAs must be executed before live patient data touches third-party APIs
- Maintain this register — auditors will ask for it
- See [DATA_FLOW.md](DATA_FLOW.md) for details on what PHI is sent to each service
- See [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) for breach notification obligations under PIPEDA
