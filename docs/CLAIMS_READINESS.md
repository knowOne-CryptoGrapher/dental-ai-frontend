# CDAnet Claims Readiness
**Applies to:** Dental AI Backend (dental-ai-backend)
**Phase:** CDAnet scaffolding — not full protocol implementation or certification
**Last updated:** 2026-05-30

---

## 1. CDAnet Fields in the Claim Model

All fields live on `InsuranceClaim` in `backend/models.py`.  They are optional at creation and populated progressively as the claim moves through the lifecycle.

### Subscriber & patient info

| Field | Required for submission | Purpose |
|---|---|---|
| `subscriber_last_name` | No | Subscriber (plan holder) last name |
| `subscriber_first_name` | No | Subscriber first name |
| `subscriber_policy_number` | **Yes** | Primary insurance policy number for CDAnet routing |
| `subscriber_certificate_number` | **Yes** | Certificate/member number within the policy |
| `relationship_to_subscriber` | No | `self`, `spouse`, `child`, `other` |

### Carrier routing

| Field | Required for submission | Purpose |
|---|---|---|
| `carrier_id` | **Yes** | CDAnet carrier code — determines routing to the correct carrier endpoint |
| `division_number` | No | Carrier division, required by some carriers |
| `practice_province` | **Yes** | Province of the submitting practice — CDAnet routing rules vary by province |

### CDAnet transaction metadata

| Field | Required for submission | Purpose |
|---|---|---|
| `cdanet_version` | **Yes** | CDAnet protocol version — defaults to `"4.1"` |
| `transaction_type` | **Yes** | One of: `claim`, `reversal`, `eligibility`, `predetermination` |
| `claim_reference_number` | No | Assigned by carrier on response; stored for status inquiry and reversals |
| `network_reference_number` | No | Network-assigned reference number (some carriers) |

### Adjudication details (populated from carrier response)

| Field | Source | Purpose |
|---|---|---|
| `adjudication_code` | Carrier response | `A` Accepted, `R` Rejected, `E` Error, `P` Pending |
| `explanation_codes` | Carrier response | List of explanation codes (see `cdanet_codes.py`) |
| `amount_approved` | Carrier response | Dollar amount approved by the carrier |
| `amount_patient_responsibility` | Carrier response | Portion owed by the patient |

### Submission tracking

| Field | Purpose |
|---|---|
| `submission_attempts` | Incremented on each submit; required for CDAnet retry rules |
| `last_submitted_at` | Timestamp of most recent submission attempt |
| `last_error_message` | Human-readable error description — never raw CDAnet codes |

### Claim lifecycle states

```
draft → ready_to_submit → submitted → accepted │ rejected │ error → paid │ reversed
```

| Status | Meaning |
|---|---|
| `draft` | Claim created, not yet validated or submitted |
| `ready_to_submit` | All required CDAnet fields present; ready to send |
| `submitted` | Transmitted to carrier; awaiting adjudication |
| `accepted` | Carrier accepted; `amount_approved` populated |
| `rejected` | Carrier rejected; `explanation_codes` explain why |
| `reversed` | Previously accepted claim has been reversed |
| `paid` | Payment confirmed |
| `error` | Unexpected carrier response or transport error |

---

## 2. Module Roles

### `backend/cdanet/cdanet_mapper.py`
- **`validate_cdanet_readiness(claim: dict) → list[str]`** — checks all fields required for CDAnet submission; returns human-readable messages for each missing field. Callable independently so the frontend can show what's missing before the user clicks Submit.
- **`build_cdanet_request(claim: dict) → dict`** — validates then builds a CDAnet v4.1 request payload. Raises `ValueError` on missing fields. Never logs the payload.
- **`parse_cdanet_response(raw: dict) → CdanetResponse`** — converts a raw carrier response dict into a typed `CdanetResponse` model. Never logs `raw`.
- **`CdanetResponse`** — Pydantic model for typed carrier responses. `raw` field is stored internally only; never logged or returned across practices.

### `backend/cdanet/cdanet_codes.py`
- **`RESPONSE_CODES`** — maps CDAnet adjudication codes to English labels (`"A"` → `"Accepted"`, etc.)
- **`EXPLANATION_CODES`** — maps two-digit explanation codes to human-readable messages
- **`REVERSAL_REASON_CODES`** — maps reversal reason codes to descriptions
- **`interpret_cdanet_response(claim, response, db) → InternalClaimStatus`** — the single authoritative point where a carrier response changes claim status. Mutates the claim dict in-place, writes an audit log entry, and returns an `InternalClaimStatus` enum value.

### `backend/insurance/itrans_client.py`
- Transport stub for ITRANS 2.0 / CDAnet ICD network calls.
- Calls `validate_cdanet_readiness` before attempting transport (defense-in-depth; the router also validates).
- Calls `build_cdanet_request` to construct the payload.
- Calls `parse_cdanet_response` to interpret the raw response.
- All methods are stubs returning mock responses. Will contain the actual ICD integration when CDA certification is pursued.

---

## 3. Response Interpretation Flow

```
Carrier response (raw dict)
    │
    ▼
parse_cdanet_response(raw)  ──→  CdanetResponse
    │                              (typed, PHI-safe)
    ▼
interpret_cdanet_response(claim, response, db)
    │  • Updates claim.status
    │  • Populates adjudication_code, explanation_codes, amounts
    │  • Writes audit_log entry (codes + amounts only, no PHI)
    ▼
InternalClaimStatus  (ACCEPTED | REJECTED | PENDING | ERROR)
    │
    ▼
Router builds user-facing response
    • RESPONSE_CODES[adjudication_code]   →  "Accepted" / "Rejected" / …
    • EXPLANATION_CODES[code]             →  human-readable reason per code
    • Raw CDAnet codes are never exposed directly to the frontend
```

---

## 4. CDAnet Certification Checklist

- [ ] CDAnet version 4.1 field compliance confirmed against CDA specification
- [ ] Test carrier ID and test transaction submission passing CDA test suite
- [ ] All response codes handled (not just A/R/E/P — full code set from CDA documentation)
- [ ] All explanation codes mapped to user-facing messages
- [ ] Reversal flow implemented and tested with `REVERSAL_REASON_CODES`
- [ ] PHI never logged in raw CDAnet payloads
- [ ] Audit trail complete for all claim lifecycle events:
  - `claim_created` on POST /insurance/claims
  - `claim_updated` on PUT /insurance/claims/:id
  - `claim_submitted` on POST /insurance/claims/:id/submit
  - `claim_status_checked` on GET /insurance/claims/:id/status
  - `claim_response_received` inside `interpret_cdanet_response`
  - `claim_reversed` on POST /insurance/claims/:id/reverse
  - `claim_validation_failed` when `validate_cdanet_readiness` returns errors
- [ ] Data residency confirmed — production on Canadian GCP region (`northamerica-northeast1`)
- [ ] DPA in place with ITRANS/CDA integration partner
- [ ] Conformance testing passed with CDA-provided test cases

---

## 5. Note on Certification

> CDAnet certification requires submission to the Canadian Dental Association's conformance testing process. The scaffolding in this codebase defines the correct data shapes, mapping layer, and audit trail. Full certification will require: replacing stub transports in `itrans_client.py` with the actual ICD integration, passing CDA-provided test cases for all transaction types, and completing the checklist above.

---

## Related Documents

- [SECURITY.md](SECURITY.md) — PHI handling and redaction controls
- [RETENTION.md](RETENTION.md) — Audit log retention (7-year minimum for dental records)
- [DATA_FLOW.md](DATA_FLOW.md) — Where PHI enters, moves, and exits the system
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — Breach response and PIPEDA notification
