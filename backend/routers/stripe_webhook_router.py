# backend/routers/stripe_webhook_router.py
"""
Stripe webhook handler.

Stripe POSTs every billing event here. We:
  • Verify the signature
  • Promote/demote practices based on subscription state
  • Attach stripe_customer_id + stripe_subscription_id to the practice
    on first checkout completion
  • Mark practice billing_status=past_due on payment_failed
  • Mark practice billing_status=cancelled on subscription deleted

Mounted at POST /api/webhook/stripe (singular).
"""
from __future__ import annotations
import os
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException

from auth import get_db
import stripe as stripe_sdk
from services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stripe_webhook"])

STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
stripe_sdk.api_key = STRIPE_API_KEY

PRICE_TO_PLAN: dict[str, str] = {
    k: v
    for k, v in {
        os.environ.get("STRIPE_PRICE_BASIC", ""):        "basic",
        os.environ.get("STRIPE_PRICE_PROFESSIONAL", ""): "professional",
        os.environ.get("STRIPE_PRICE_ENTERPRISE", ""):   "enterprise",
        os.environ.get("STRIPE_PRICE_ELITE", ""):        "elite",
    }.items()
    if k
}


@router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
  """
  Stripe sends webhook events here. We verify the signature using the
  Stripe SDK, then route on the event type and update the practice /
  transaction record.
  """
  if not STRIPE_API_KEY or not STRIPE_WEBHOOK_SECRET:
    raise HTTPException(status_code=503, detail="Stripe not configured")

  raw_body = await request.body()
  signature = request.headers.get("Stripe-Signature", "")

  try:
    event = stripe_sdk.Webhook.construct_event(
      payload=raw_body,
      sig_header=signature,
      secret=STRIPE_WEBHOOK_SECRET,
    )
  except stripe_sdk.error.SignatureVerificationError as e:
    logger.error(f"Stripe webhook signature failure: {e}")
    raise HTTPException(status_code=400, detail="Invalid signature")
  except Exception as e:
    logger.error(f"Stripe webhook parse error: {e}")
    raise HTTPException(status_code=400, detail="Invalid payload")

  event_dict = json.loads(raw_body)

  event_type = event_dict.get("type", "unknown")
  obj = (event_dict.get("data") or {}).get("object") or {}
  session_id = obj.get("id") if event_type.startswith("checkout.session") else obj.get("checkout_session_id")
  payment_status = obj.get("payment_status") or obj.get("status")
  metadata = obj.get("metadata") or {}

  logger.info(f"💳 Stripe webhook: {event_type} session={session_id} status={payment_status}")

  db = get_db()

  # Deduplicate: Stripe delivers at-least-once; skip already-processed events
  event_id = event_dict.get("id")
  if event_id:
      existing = await db.stripe_webhook_events.find_one({"event_id": event_id})
      if existing:
          logger.info("stripe_webhook_duplicate_skipped", extra={"event_id": event_id})
          return {"status": "ok", "skipped": True}

  # Persist raw event for audit / replay debugging
  await db.stripe_webhook_events.insert_one(
    {
      "event_id": event_dict.get("id"),
      "event_type": event_type,
      "session_id": session_id,
      "payment_status": payment_status,
      "metadata": metadata,
      "received_at": datetime.now(timezone.utc).isoformat(),
      "raw": event_dict,
    }
  )

  # Most-important event: a Checkout completed → attach customer+sub IDs to practice
  if event_type == "checkout.session.completed" and session_id:
    await _on_checkout_completed(db, session_id, metadata)

  # Subscription status changes (recurring billing)
  if event_type.startswith("customer.subscription.") or event_type.startswith("invoice."):
    await _sync_subscription_state(db, event_type, obj)

  return {"received": True, "event_type": event_type}


async def _on_checkout_completed(db, session_id: str, metadata: dict):
  """First successful payment for this session — link customer+sub to practice."""
  practice_id = metadata.get("practice_id")
  plan_id = metadata.get("plan_id")
  if not practice_id:
    logger.warning(
      f"Stripe webhook completed without practice_id metadata: {session_id}"
    )
    return

  # Pull the full Stripe session for the customer / subscription IDs
  try:
    full = stripe_sdk.checkout.Session.retrieve(session_id).to_dict_recursive()
    stripe_customer_id = full.get("customer")
    stripe_subscription_id = full.get("subscription")
  except Exception as e:
    logger.error(f"Failed to retrieve Stripe session {session_id}: {e}")
    stripe_customer_id = None
    stripe_subscription_id = None

  update = {
    "billing_status": "active",
    "last_payment_at": datetime.now(timezone.utc).isoformat(),
  }
  if plan_id:
    update["subscription_plan"] = plan_id
  if stripe_customer_id:
    update["stripe_customer_id"] = stripe_customer_id
  if stripe_subscription_id:
    update["stripe_subscription_id"] = stripe_subscription_id

  await db.practices.update_one({"id": practice_id}, {"$set": update})

  if stripe_customer_id:
    await db.billing_customers.update_one(
      {"practice_id": practice_id},
      {
        "$set": {
          "stripe_customer_id": stripe_customer_id,
          "plan": plan_id or "basic",
          "status": "active",
          "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "$setOnInsert": {
          "id": str(uuid.uuid4()),
          "created_at": datetime.now(timezone.utc).isoformat(),
        },
      },
      upsert=True,
    )

  # Idempotent transaction promotion
  txn = await db.payment_transactions.find_one(
    {"session_id": session_id},
    {"_id": 0, "promoted_at": 1, "plan_id": 1},
  )
  if txn and not txn.get("promoted_at"):
    await db.payment_transactions.update_one(
      {"session_id": session_id},
      {
        "$set": {
          "promoted_at": datetime.now(timezone.utc).isoformat(),
          "payment_status": "paid",
          "status": "complete",
          "stripe_customer_id": stripe_customer_id,
          "stripe_subscription_id": stripe_subscription_id,
        }
      },
    )
  logger.info(
    f"✅ Practice {practice_id} → {plan_id} (customer={stripe_customer_id})"
  )


async def _sync_subscription_state(db, event_type: str, obj: dict):
  """Flip practice.billing_status (and subscription_plan on plan change) when
  Stripe tells us the subscription state changed.
  Stripe sends the subscription object inside event.data.object."""
  customer_id = obj.get("customer")
  if not customer_id:
    return

  new_status: str | None = None
  new_plan:   str | None = None

  if event_type == "customer.subscription.deleted":
    new_status = "cancelled"
  elif event_type == "customer.subscription.updated":
    stripe_status = obj.get("status")
    if stripe_status == "past_due":
      new_status = "past_due"
    elif stripe_status == "active":
      new_status = "active"
    elif stripe_status in ("canceled", "unpaid"):
      new_status = "cancelled"
    try:
      price_id = obj["items"]["data"][0]["price"]["id"]
      new_plan = PRICE_TO_PLAN.get(price_id)
    except (KeyError, IndexError, TypeError):
      pass
  elif event_type == "invoice.payment_failed":
    new_status = "past_due"
  elif event_type == "invoice.paid":
    new_status = "active"

  # Snapshot practice before update to capture old plan for plan_changed notification
  _practice_snap: dict | None = None
  if new_status == "past_due" or new_plan is not None:
    _practice_snap = await db.practices.find_one(
      {"stripe_customer_id": customer_id},
      {"_id": 0, "id": 1, "name": 1, "subscription_plan": 1, "settings": 1},
    )

  if new_status:
    update_fields: dict = {
      "billing_status": new_status,
      "billing_status_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if new_plan:
      update_fields["subscription_plan"] = new_plan
    if event_type == "invoice.paid":
      update_fields["last_payment_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.practices.update_one(
      {"stripe_customer_id": customer_id},
      {"$set": update_fields},
    )
    if result.matched_count:
      logger.info(
        f"🔄 Stripe → practice billing_status={new_status} plan={new_plan} (customer={customer_id})"
      )
      # Non-blocking admin billing notifications
      if _practice_snap:
        try:
          _frontend_url = os.getenv("FRONTEND_URL", "https://app.dentalai.ca")
          _admin_email = (_practice_snap.get("settings") or {}).get("admin_email")
          _notif = (_practice_snap.get("settings") or {}).get("email_notifications") or {}
          _practice_name = _practice_snap.get("name", "Your Practice")
          _practice_id = _practice_snap.get("id", "")
          if _admin_email:
            if new_status == "past_due" and _notif.get("billing_alerts", True):
              await email_service.send_admin_notification(
                db=db,
                practice_id=_practice_id,
                admin_email=_admin_email,
                template_name="billing_past_due",
                subject=f"Payment Past Due — {_practice_name}",
                template_vars={
                  "practice_name": _practice_name,
                  "plan_name": (_practice_snap.get("subscription_plan") or "unknown").title(),
                  "amount_due": "See billing portal",
                  "due_date": "Please update your payment method",
                  "portal_url": f"{_frontend_url}/billing",
                  "dashboard_url": f"{_frontend_url}/dashboard",
                },
              )
            if new_plan and _notif.get("plan_change_alerts", True):
              await email_service.send_admin_notification(
                db=db,
                practice_id=_practice_id,
                admin_email=_admin_email,
                template_name="plan_changed",
                subject=f"Subscription Plan Changed — {_practice_name}",
                template_vars={
                  "practice_name": _practice_name,
                  "old_plan": (_practice_snap.get("subscription_plan") or "previous plan").title(),
                  "new_plan": new_plan.title(),
                  "effective_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                  "dashboard_url": f"{_frontend_url}/dashboard",
                },
              )
        except Exception as _exc:
          logger.error(
            "admin_email_billing_notification_error",
            extra={"error": str(_exc), "customer_id": customer_id},
          )
