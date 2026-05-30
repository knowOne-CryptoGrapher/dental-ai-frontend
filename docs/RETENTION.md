# Log and Data Retention Policy
**Applies to:** Dental AI Backend (dental-ai-backend)
**Jurisdiction:** Canada — PIPEDA, provincial dental records legislation
**Last updated:** 2026-05-30

---

## Retention Schedule

| Data type | Collection / store | Minimum retention | Maximum retention | Enforcement |
|---|---|---|---|---|
| Audit logs | `audit_logs` (MongoDB) | **7 years** | Indefinite | No TTL index — retained permanently |
| Security event logs | `security_events` (MongoDB) | **1 year** | 2 years | TTL index (see below) |
| Application / request logs | Cloud Logging (GCP) | **90 days** | 90 days | Cloud Logging retention setting |
| Call transcripts | `call_logs.transcript` (MongoDB) | N/A | **90 days** unless legally required longer | TTL index on `call_logs`; anonymise after window |
| Patient records | `patients` (MongoDB) | 7 years from last visit | Per practice jurisdiction | Managed by practice admin |

---

## Why 7 Years for Audit Logs

Canadian dental regulatory colleges (RCDSO, CDSBC, CDSPI, etc.) require patient records to be retained for a minimum of **7 years** from the date of the last entry, or until the patient reaches age 18 (whichever is later). Audit logs tie directly to patient record access and mutation events, so they share this retention floor.

---

## TTL Index Configuration

Run these once against the production database. **Do not add a TTL index to `audit_logs`.**

```python
# Application logs collection (90 days = 7 776 000 seconds)
db.application_logs.create_index("timestamp", expireAfterSeconds=7776000)

# Security events (1 year = 31 536 000 seconds)
db.security_events.create_index("timestamp", expireAfterSeconds=31536000)

# Call transcripts — anonymise after 90 days
# Option A: TTL deletes the entire document (only if transcripts are in a dedicated collection)
# db.call_transcripts.create_index("created_at", expireAfterSeconds=7776000)

# Option B: Null out the transcript field after 90 days (preferred — preserves call metadata)
# Implement as a scheduled Cloud Run Job or Atlas Trigger:
#   db.call_logs.update_many(
#       {"created_at": {"$lt": datetime.utcnow() - timedelta(days=90)},
#        "transcript": {"$ne": None}},
#       {"$set": {"transcript": None, "transcript_anonymised_at": datetime.utcnow()}}
#   )
```

---

## Audit Logs — NO TTL Index

`audit_logs` must **never** have a TTL index. Audit records are the evidence trail for regulatory compliance and breach investigations. Loss of audit records during a compliance review or litigation hold is a serious risk.

Verify no TTL index exists:
```python
db.audit_logs.index_information()
# Confirm no index has an "expireAfterSeconds" field
```

---

## Cloud Logging Retention

Set the retention period for the `_Default` log bucket in Cloud Logging to **90 days**:

```bash
gcloud logging buckets update _Default \
  --location=global \
  --retention-days=90 \
  --project dental-ai-backend
```

For audit / security log sinks (if forwarded to a dedicated bucket), set retention to **365 days** minimum.

---

## Call Transcript Handling

Call transcripts stored in `call_logs.transcript` are **PHI**. They must be:

1. **Anonymised (transcript field set to null) after 90 days** unless the practice is subject to a legal hold or a longer provincial requirement applies.
2. **Never written to application logs** — the `redact_phi()` helper covers the `transcript` field.
3. **Access-controlled** — only `admin`, `provider`, and `auditor` roles may retrieve transcripts; the `practice_id` scope is enforced at the DB query level.

If a practice requires transcripts beyond 90 days (e.g., for an ongoing insurance dispute), the practice admin must flag the record explicitly. Flagged records are excluded from the anonymisation job.

---

## Enforcement Responsibilities

| Responsibility | Owner |
|---|---|
| MongoDB TTL indexes | Backend engineering — run once on initial deploy; verify quarterly |
| Cloud Logging retention setting | GCP project owner — set at environment creation |
| Transcript anonymisation job | Backend engineering — scheduled Cloud Run Job |
| Compliance review | Practice owner / DPO — annually |

---

## Related Documents

- [SECURITY.md](SECURITY.md) — PHI handling and log redaction rules
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) — breach notification timeline
