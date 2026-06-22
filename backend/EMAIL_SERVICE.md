# Email Service — Architecture & Operations Guide

## Architecture Overview

All transactional email in Dental AI flows through a single class: `EmailService` in
`backend/services/email_service.py`. It is exposed as a module-level singleton (`email_service`)
imported by any router that needs to send email.

```
Router
  └── await email_service.send(to_email, subject, template_name, template_vars, practice_id)
        ├── _render(template_name, ...)    # loads .html + .txt, applies string.Template
        └── asyncio.to_thread(client.send_email, ...)   # boto3 SES, non-blocking
```

**Why SES?**
- First-class Canadian deliverability (us-east-1 serves Canada)
- Per-message tags enable practice-level bounce/complaint attribution
- SNS event delivery is more reliable than polling for bounce/complaint data
- No per-message cost above the SES sending charge

**Why not Jinja2?**
Python's built-in `string.Template` keeps dependencies minimal and prevents template
injection attacks (no filters, no `{% exec %}`, no arbitrary expressions).

---

## Adding a New Email Template

1. **Create the HTML body** at `backend/templates/email/<template_name>.html`.
   Write only the inner body — the base layout is applied automatically.
   Use `$variable_name` for substitution slots. Escape literal `$` as `$$`.

2. **Create the plain text version** at `backend/templates/email/<template_name>.txt`.
   This is standalone (no base wrapper). Use the same `$variable_name` slots.

3. **Call `email_service.send()`** from your router:

   ```python
   from services.email_service import email_service

   await email_service.send(
       to_email=user_email,
       subject="Your subject line",
       template_name="<template_name>",   # matches the filename stem
       template_vars={
           "practice_name": practice.get("name"),
           "custom_var": "value",
       },
       practice_id=practice_id,
   )
   ```

4. **Wrap in try/except** — email failure must never block your primary operation:

   ```python
   try:
       await email_service.send(...)
   except Exception as exc:
       logger.error(f"email failed: {exc}")
   ```

### Available base template variables

These are automatically injected by `EmailService._render()` and do not need to be
provided in `template_vars`:

| Variable | Value |
|---|---|
| `$year` | Current 4-digit year |
| `$footer_text` | From `practice_branding["footer_text"]`, defaults to `"Front Desk Dental AI"` |
| `$body_content` | The rendered inner HTML (base.html only — do not use in body templates) |

---

## Adding Practice Branding

Pass `practice_branding` to `email_service.send()`:

```python
await email_service.send(
    ...
    practice_branding=practice.get("settings", {}).get("branding", {}),
    reply_to=practice.get("settings", {}).get("branding", {}).get("reply_to_email"),
)
```

Supported branding fields (stored under `practice.settings.branding`):

| Field | Effect |
|---|---|
| `footer_text` | Replaces the default footer line in every email |
| `reply_to_email` | Sets the Reply-To header (does not change the From identity) |

**Important:** The `From` address is always `SES_FROM_NAME <SES_FROM_EMAIL>` — a practice
can never change who the email appears to be from. Only the `Reply-To` header is practice-controlled.

---

## Testing Locally Without SES Credentials

When `SES_ACCESS_KEY_ID` or `SES_SECRET_ACCESS_KEY` are empty, the SES client is not
initialised at import time. Calls to `email_service.send()` will:

1. Pass the practice_id check
2. Fail on `_get_client()` with `RuntimeError("SES credentials not configured")`
3. Be caught by the outer `except Exception` block
4. Return `False` and log `email_unexpected_error`

To verify template rendering without sending real email, call `email_service._render()`
directly in a Python shell:

```python
from services.email_service import email_service
html, txt = email_service._render(
    "invite_staff",
    {"practice_name": "Test Clinic", "role": "staff",
     "invite_url": "http://localhost:3000/invite/abc", "expiry_hours": "24"},
    None,
)
print(txt)
```

To run unit tests, mock boto3 entirely — see `backend/tests/test_email_service.py`.

---

## SES Sandbox vs Production

In **sandbox mode** (default for new AWS accounts):
- Email can only be sent to verified email addresses
- Sending to unverified addresses silently fails with `MessageRejected`
- Use sandbox for development; test with your own `@frontdeskdentalai.com` address

To request **production access**:
1. AWS Console → SES → Account Dashboard → "Request production access"
2. Provide use-case description (transactional email for dental clinic SaaS)
3. Estimated volume and bounce-handling plan (already implemented via SNS webhook)
4. AWS typically approves in 24–48 hours

Once approved, sending quota is 50,000/day by default (requestable higher).

---

## SNS Webhook Setup

The `/api/webhooks/ses` endpoint receives bounce, complaint, delivery, and reject events
from AWS SNS. To wire it up:

1. **Create an SNS topic** in AWS Console:
   - Name: `dental-ai-email-events`
   - Type: Standard
   - Copy the ARN into `SES_SNS_TOPIC_ARN` in your `.env`

2. **Subscribe the endpoint** to the topic:
   - Protocol: HTTPS
   - Endpoint: `https://api.frontdeskdentalai.com/api/webhooks/ses`
   - AWS will POST a `SubscriptionConfirmation` message — the router confirms it automatically

3. **Configure SES to publish to the topic**:
   - SES Console → Configuration Sets → Create or select a configuration set
   - Add destination: SNS → select `dental-ai-email-events` topic
   - Enable: Bounce, Complaint, Delivery, Send, Reject events
   - Set this configuration set as the default in SES account-level settings

4. **Verify** by sending a test email; check `email_events` collection in MongoDB for a
   `Delivery` event within ~30 seconds.

---

## Multi-Tenant Isolation Rules

**What is permitted:**
- A practice can configure `reply_to_email` for reply routing
- A practice can set `footer_text` for branding
- Each send is tagged with `practice_id` in SES message tags for attribution

**What is never permitted:**
- A practice cannot change the `From` address — all email comes from `SES_FROM_EMAIL`
- A practice cannot access another practice's email events — `email_events` documents
  carry `practice_id` and must be filtered by it in any query
- PHI must never appear in the `recipient` field of `email_events` — it is masked to
  the first 3 characters before storage. The full address exists only in the `raw_event`
  field which is never logged, only persisted.

**Enforcement:**
`email_service.send()` requires a non-empty `practice_id` on every call. Calling without
one returns `False` immediately and logs `email_blocked_no_tenant`. This is a hard guard
against accidentally sending cross-tenant email.
