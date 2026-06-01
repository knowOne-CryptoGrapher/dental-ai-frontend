# Privacy Policy
Version 1.0 — Last updated: 2026-06-01

---

## 1. What data we collect

- Practice information (name, address, province, contact details)
- Patient appointment and insurance data entered by clinic staff
- Call recordings and transcripts (when using the AI receptionist)
- Authentication credentials (hashed — never stored in plaintext)
- Usage logs (anonymized)

---

## 2. Why we collect it

- To provide the AI receptionist and practice management services
- To process insurance claims via CDAnet/iTRANS
- To comply with dental regulatory requirements

---

## 3. Where data is stored

All patient data is stored in Canada:

| Province group | Region | Infrastructure |
|---|---|---|
| BC, AB, SK, MB | Calgary | Google Cloud `northamerica-west2` |
| ON, QC, NB, NS, PE, NL, NU | Montreal | Google Cloud `northamerica-northeast1` |

Data does not leave Canada except as described in cross-border processing below.

---

## 4. Cross-border processing disclosure

Some data is processed by third-party AI providers outside Canada for the purpose of generating AI responses. Before being sent, patient names, contact details, and health identifiers are replaced with anonymized placeholders. Raw patient data is never transmitted to third-party AI providers.

---

## 5. Vendors used and DPA status

| Vendor | Purpose | PHI sent | DPA status |
|---|---|---|---|
| MongoDB Atlas | Data storage | Full patient records | In place |
| Google Cloud | Compute and infrastructure | Encrypted secrets only | In place |
| Stripe | Billing only | Billing contact, no clinical data | In place |
| OpenAI | AI inference | Anonymized prompts only | In progress |
| Anthropic | AI inference | Anonymized prompts only | In progress |
| Groq | AI inference | Anonymized prompts only | In progress |
| Retell | Voice call handling | Call audio and transcripts | In progress |

---

## 6. Data retention

| Data type | Retention period |
|---|---|
| Patient records | 7 years from last visit (per provincial dental regulations) |
| Audit logs | 7 years minimum |
| Call transcripts | 90 days, then anonymized |
| Usage logs | 90 days |

---

## 7. Data deletion

- Practices may request deletion of their data by contacting support
- Patient data cannot be deleted if retention is required by law
- Deletion requests are processed within 30 days

---

## 8. Individual rights (PIPEDA)

- You have the right to access personal information we hold about you
- You have the right to correct inaccurate information
- You have the right to request deletion (subject to legal retention requirements)
- You have the right to withdraw consent, subject to legal and contractual restrictions

To exercise these rights, contact: privacy@dentalai.ca

---

## 9. Contact information

- Privacy Officer: privacy@dentalai.ca
- Mailing address: [to be completed before launch]
