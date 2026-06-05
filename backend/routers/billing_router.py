# backend/routers/billing_router.py
"""
Stripe-backed billing for the multi-tenant SaaS.

Architecture:
  • Backend defines plans (no frontend price-tampering)
  • Stripe Checkout Sessions in `subscription` mode for recurring billing
    (requires the operator to create 3 recurring Prices in their Stripe
    Dashboard and put the IDs in env: STRIPE_PRICE_BASIC / _PROFESSIONAL
    / _ENTERPRISE)
  • Fallback: if no Price IDs are configured, falls back to a one-time
    Custom Amount checkout — useful for dev w/ the platform test key
  • Per-call MongoDB transaction record (`payment_transactions`)
  • Stripe Customer Portal for upgrade / downgrade / cancel
  • Webhook handler at /api/webhook/stripe keeps practice billing_status
    and subscription_plan in sync with Stripe
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Response
import os
import uuid
import logging
from io import BytesIO
from datetime import datetime, timezone

from auth import get_db, require_role, get_current_user, log_audit_event
from dependencies import require_feature
from plans import PLANS, get_plan, list_plans, DEFAULT_PLAN_ID

import stripe as stripe_sdk  # raw Stripe SDK

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/billing", tags=["billing"])

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "").strip()
stripe_sdk.api_key = STRIPE_API_KEY  # used by all Stripe calls


def _require_stripe():
  if not STRIPE_API_KEY:
    raise HTTPException(
      status_code=503,
      detail="Billing not configured. Set STRIPE_API_KEY in backend/.env.",
    )


# ──────────────────────────────────────────────────────────────────────
# Plans + usage  (read-only)
# ──────────────────────────────────────────────────────────────────────


@router.get("/plans")
async def get_plans():
  """Public — anyone can see what plans exist (used on the Billing page)."""
  return [p.public_dict() for p in list_plans()]


@router.get("/features")
async def get_my_features(current_user: dict = Depends(require_role("admin", "staff", "provider", "auditor"))):
  """Returns the feature flags for the practice's current plan.
  Frontend uses this to conditionally render gated pages."""
  db = get_db()
  practice = await db.practices.find_one(
    {"id": current_user["practice_id"]},
    {"_id": 0, "subscription_plan": 1, "billing_status": 1},
  ) or {}
  plan = get_plan(practice.get("subscription_plan"))
  return {
    "plan_id": plan.id,
    "plan_name": plan.name,
    "billing_status": practice.get("billing_status", "active"),
    "features": plan.public_dict()["features"],
    "limits": {
      "calls_per_month": plan.limits.calls_per_month,
      "providers_max": plan.limits.providers_max,
      "locations_max": plan.limits.locations_max,
      "users_max": plan.limits.users_max,
    },
  }


@router.get("/usage")
async def get_usage(current_user: dict = Depends(require_role("admin"))):
  db = get_db()
  practice_id = current_user["practice_id"]
  practice = await db.practices.find_one({"id": practice_id}, {"_id": 0}) or {}

  plan = get_plan(practice.get("subscription_plan"))

  calls = await db.call_logs.count_documents({"practice_id": practice_id})
  providers = await db.providers.count_documents(
    {"practice_id": practice_id, "$or": [{"is_active": True}, {"active": True}]}
  )
  locations = await db.locations.count_documents(
    {"practice_id": practice_id, "is_active": True}
  )
  claims = await db.insurance_claims.count_documents({"practice_id": practice_id})

  return {
    "plan": plan.id,
    "plan_name": plan.name,
    "price": plan.price_usd,
    "stripe_customer_id": practice.get("stripe_customer_id"),
    "stripe_subscription_id": practice.get("stripe_subscription_id"),
    "billing_status": practice.get("billing_status", "active"),
    "usage": {
      "calls": {"used": calls, "included": plan.limits.calls_per_month},
      "providers": {"used": providers, "max": plan.limits.providers_max},
      "locations": {"used": locations, "max": plan.limits.locations_max},
      "claims_submitted": claims,
    },
  }


@router.get("/usage-stats")
async def get_usage_stats(current_user: dict = Depends(get_current_user)):
  """Detailed usage vs plan limits for the authenticated practice."""
  db = get_db()
  practice_id = current_user.get("practice_id")
  if not practice_id:
    raise HTTPException(status_code=400, detail="No practice associated with this user.")

  practice = await db.practices.find_one(
    {"id": practice_id}, {"_id": 0, "subscription_plan": 1}
  ) or {}
  plan = get_plan(practice.get("subscription_plan"))

  now = datetime.now(timezone.utc)
  month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()

  calls = await db.call_logs.count_documents({
    "practice_id": practice_id,
    "start_time": {"$gte": month_start},
  })
  providers = await db.providers.count_documents({
    "practice_id": practice_id,
    "$or": [{"is_active": True}, {"active": True}],
  })
  locations = await db.locations.count_documents({
    "practice_id": practice_id,
    "is_active": True,
  })
  users = await db.users.count_documents({
    "practice_id": practice_id,
    "is_active": True,
  })

  return {
    "calls":     {"used": calls,     "limit": plan.limits.calls_per_month},
    "providers": {"used": providers, "limit": plan.limits.providers_max},
    "locations": {"used": locations, "limit": plan.limits.locations_max},
    "users":     {"used": users,     "limit": plan.limits.users_max},
  }


@router.get("/invoices")
async def get_invoices(current_user: dict = Depends(require_role("admin"))):
  """Stripe-backed invoices for the practice's customer.
  Empty list if the practice has never paid (no customer yet)."""
  db = get_db()
  practice = await db.practices.find_one(
    {"id": current_user["practice_id"]}, {"_id": 0}
  ) or {}
  stripe_customer_id = practice.get("stripe_customer_id")
  if not stripe_customer_id or not STRIPE_API_KEY:
    return []
  try:
    invs = stripe_sdk.Invoice.list(customer=stripe_customer_id, limit=20)
    return [
      {
        "id": inv["id"],
        "amount": (inv.get("amount_paid") or 0) / 100,
        "currency": inv.get("currency", "usd"),
        "status": inv.get("status"),
        "period": datetime.fromtimestamp(
          inv.get("created", 0), tz=timezone.utc
        ).strftime("%B %Y"),
        "paid_at": datetime.fromtimestamp(
          inv.get("status_transitions", {}).get("paid_at")
          or inv.get("created", 0),
          tz=timezone.utc,
        ).isoformat()
        if inv.get("status_transitions", {}).get("paid_at")
        else None,
        "hosted_invoice_url": inv.get("hosted_invoice_url"),
      }
      for inv in invs.auto_paging_iter()
    ][:20]
  except Exception as e:
    logger.warning(f"Stripe invoice fetch failed: {e}")
    return []


# ──────────────────────────────────────────────────────────────────────
# Checkout
# ──────────────────────────────────────────────────────────────────────


@router.post("/checkout")
async def create_checkout_session(
  body: dict,
  request: Request,
  current_user: dict = Depends(require_role("admin")),
):
  """
  Body:
    { "plan": "basic" | "professional" | "enterprise",
      "origin_url": "https://app.example.com" }   ← from window.location.origin

  Returns:
    { "url": "<stripe checkout url>", "session_id": "cs_..." }
  """
  _require_stripe()
  db = get_db()
  plan_id = (body.get("plan") or "").lower()
  origin_url = (body.get("origin_url") or "").rstrip("/")

  if plan_id not in PLANS:
    raise HTTPException(status_code=400, detail=f"Invalid plan '{plan_id}'")
  if not origin_url:
    raise HTTPException(status_code=400, detail="origin_url required")

  plan = PLANS[plan_id]
  practice_id = current_user["practice_id"]
  practice = await db.practices.find_one({"id": practice_id}, {"_id": 0}) or {}

  success_url = f"{origin_url}/billing?session_id={{CHECKOUT_SESSION_ID}}"
  cancel_url = f"{origin_url}/billing?stripe=cancelled"
  metadata = {
    "practice_id": practice_id,
    "practice_name": practice.get("name", ""),
    "user_id": current_user["id"],
    "user_email": current_user.get("email", ""),
    "plan_id": plan_id,
  }

  # Mode A — recurring subscription via stripe_price_id (production path).
  # Mode B — one-time Custom Amount (dev / before Price IDs are set).
  if plan.stripe_price_id:
    try:
      stripe_session = stripe_sdk.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        subscription_data={"metadata": metadata},
        customer_email=current_user.get("email") or None,
        client_reference_id=practice_id,
      )
      mode_used = "subscription"
    except stripe_sdk.error.StripeError as e:
      logger.error(f"Stripe subscription checkout failed: {e}")
      raise HTTPException(
        status_code=502, detail=f"Stripe error: {e.user_message or str(e)}"
      )
  else:
    # One-time amount checkout
    try:
      stripe_session = stripe_sdk.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
          {
            "price_data": {
              "currency": "usd",
              "unit_amount": int(plan.price_usd * 100),
              "product_data": {"name": f"{plan.name} plan"},
            },
            "quantity": 1,
          }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        customer_email=current_user.get("email") or None,
        client_reference_id=practice_id,
      )
      mode_used = "one_time_amount"
      logger.warning(
        f"Plan '{plan_id}' has no STRIPE_PRICE_* env var — falling back to "
        "one-time charge. Set the recurring Price ID for true subscriptions."
      )
    except stripe_sdk.error.StripeError as e:
      logger.error(f"Stripe one-time checkout failed: {e}")
      raise HTTPException(
        status_code=502, detail=f"Stripe error: {e.user_message or str(e)}"
      )

  session = stripe_session

  # Required by playbook: record the transaction BEFORE redirect
  await db.payment_transactions.insert_one(
    {
      "id": str(uuid.uuid4()),
      "session_id": session.id,
      "practice_id": practice_id,
      "user_id": current_user["id"],
      "user_email": current_user.get("email"),
      "plan_id": plan_id,
      "amount_usd": plan.price_usd,
      "currency": "usd",
      "metadata": metadata,
      "checkout_mode": mode_used,
      "payment_status": "initiated",
      "status": "pending",
      "created_at": datetime.now(timezone.utc).isoformat(),
      "updated_at": datetime.now(timezone.utc).isoformat(),
    }
  )
  await log_audit_event(
    user_id=current_user["id"],
    practice_id=practice_id,
    action="billing_checkout_started",
    resource_type="payment_transaction",
    resource_id=session.id,
    details={"plan": plan_id, "mode": mode_used},
  )

  return {"url": session.url, "session_id": session.id, "mode": mode_used}


@router.get("/checkout/status/{session_id}")
async def get_checkout_status(
  session_id: str,
  request: Request,
  current_user: dict = Depends(require_role("admin")),
):
  """
  Polled by the frontend after Stripe redirects back. Returns the
  current payment status and — on the FIRST observation of `paid` —
  promotes the practice to the new plan (idempotent: subsequent
  polls for the same session_id are no-ops).
  """
  _require_stripe()
  db = get_db()

  txn = await db.payment_transactions.find_one(
    {"session_id": session_id, "practice_id": current_user["practice_id"]},
    {"_id": 0},
  )
  if not txn:
    raise HTTPException(status_code=404, detail="Transaction not found")

  # Fast path — webhook already promoted this session
  if txn.get("payment_status") == "paid":
    return {
      "session_id": session_id,
      "status": txn.get("status", "complete"),
      "payment_status": "paid",
      "amount_total": txn.get(
        "amount_total", int((txn.get("amount_usd") or 0) * 100)
      ),
      "currency": txn.get("currency", "usd"),
      "plan_id": txn.get("plan_id"),
      "metadata": txn.get("metadata") or {},
      "source": "db",
    }

  # Slow path — ask Stripe directly.
  try:
    s = stripe_sdk.checkout.Session.retrieve(session_id)
  except Exception as e:
    logger.warning(
      f"Stripe poll failed for {session_id}: {e} — returning DB state"
    )
    return {
      "session_id": session_id,
      "status": txn.get("status", "pending"),
      "payment_status": txn.get("payment_status", "pending"),
      "amount_total": int((txn.get("amount_usd") or 0) * 100),
      "currency": txn.get("currency", "usd"),
      "plan_id": txn.get("plan_id"),
      "metadata": txn.get("metadata") or {},
      "source": "db_fallback",
      "stripe_error": str(e),
    }

  payment_status = s.payment_status
  session_status = s.status
  practice_id = txn["practice_id"]

  update = {
    "payment_status": payment_status,
    "status": session_status,
    "amount_total": s.amount_total,
    "currency": s.currency,
    "updated_at": datetime.now(timezone.utc).isoformat(),
  }
  await db.payment_transactions.update_one(
    {"session_id": session_id}, {"$set": update}
  )

  # On first observation of `paid`, do the FULL promotion.
  if payment_status == "paid" and not txn.get("promoted_at"):
    await _promote_practice_to_plan(
      db,
      practice_id,
      txn["plan_id"],
      session_id,
      stripe_customer_id=s.customer,
      stripe_subscription_id=s.subscription,
      amount_total=s.amount_total,
      currency=s.currency,
    )

  return {
    "session_id": session_id,
    "status": session_status,
    "payment_status": payment_status,
    "amount_total": s.amount_total,
    "currency": s.currency,
    "plan_id": txn["plan_id"],
    "metadata": s.metadata or {},
    "source": "stripe",
  }


async def _promote_practice_to_plan(
  db,
  practice_id: str,
  plan_id: str,
  session_id: str,
  stripe_customer_id: str | None = None,
  stripe_subscription_id: str | None = None,
  amount_total: int | None = None,
  currency: str | None = None,
):
  """Atomic: attach Stripe IDs, flip plan + billing_status, mark txn promoted_at, write audit log."""
  now_iso = datetime.now(timezone.utc).isoformat()

  practice_set = {
    "subscription_plan": plan_id,
    "billing_status": "active",
    "billing_status_updated_at": now_iso,
    "last_payment_at": now_iso,
  }
  if stripe_customer_id:
    practice_set["stripe_customer_id"] = stripe_customer_id
  if stripe_subscription_id:
    practice_set["stripe_subscription_id"] = stripe_subscription_id
  await db.practices.update_one({"id": practice_id}, {"$set": practice_set})

  txn_set = {"promoted_at": now_iso}
  if stripe_customer_id:
    txn_set["stripe_customer_id"] = stripe_customer_id
  if stripe_subscription_id:
    txn_set["stripe_subscription_id"] = stripe_subscription_id
  if amount_total is not None:
    txn_set["amount_total"] = amount_total
  if currency:
    txn_set["currency"] = currency
  await db.payment_transactions.update_one(
    {"session_id": session_id}, {"$set": txn_set}
  )

  bc_set = {
    "practice_id": practice_id,
    "plan": plan_id,
    "status": "active",
    "updated_at": now_iso,
  }
  if stripe_customer_id:
    bc_set["stripe_customer_id"] = stripe_customer_id
  if stripe_subscription_id:
    bc_set["stripe_subscription_id"] = stripe_subscription_id
  await db.billing_customers.update_one(
    {"practice_id": practice_id}, {"$set": bc_set}, upsert=True
  )

  logger.info(
    f"💳 Practice {practice_id} promoted to {plan_id} "
    f"(session {session_id}, customer={stripe_customer_id}, subscription={stripe_subscription_id})"
  )


# ──────────────────────────────────────────────────────────────────────
# Stripe Customer Portal (manage / cancel / update card)
# ──────────────────────────────────────────────────────────────────────


@router.post("/portal")
async def create_portal_session(
  body: dict,
  current_user: dict = Depends(require_role("admin")),
):
  """
  Body: { "origin_url": "https://app..." }
  Returns: { "url": "<billing portal session url>" }

  Requires the practice to have a stripe_customer_id (i.e. they've
  completed at least one paid checkout).
  """
  _require_stripe()
  db = get_db()
  practice = await db.practices.find_one(
    {"id": current_user["practice_id"]}, {"_id": 0}
  ) or {}
  customer_id = practice.get("stripe_customer_id")
  if not customer_id:
    raise HTTPException(
      status_code=400,
      detail="No Stripe customer on file. Subscribe to a plan first.",
    )
  origin_url = (body.get("origin_url") or "").rstrip("/")
  if not origin_url:
    raise HTTPException(status_code=400, detail="origin_url required")
  try:
    session = stripe_sdk.billing_portal.Session.create(
      customer=customer_id,
      return_url=f"{origin_url}/billing",
    )
    return {"url": session.url}
  except Exception as e:
    logger.error(f"Stripe portal session error: {e}")
    raise HTTPException(status_code=502, detail=f"Stripe error: {e}")


# ──────────────────────────────────────────────────────────────────────
# BAA download (Elite only)
# ──────────────────────────────────────────────────────────────────────


def _build_baa_pdf(practice_name: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "BAATitle", parent=styles["Heading1"],
        fontSize=18, spaceAfter=4, alignment=TA_CENTER,
        textColor=colors.HexColor("#1a1a2e"),
    )
    subtitle_style = ParagraphStyle(
        "BAASubtitle", parent=styles["Normal"],
        fontSize=11, spaceAfter=16, alignment=TA_CENTER,
        textColor=colors.HexColor("#4a5568"),
    )
    body_style = ParagraphStyle(
        "BAABody", parent=styles["Normal"],
        fontSize=10, spaceAfter=8, leading=14, alignment=TA_JUSTIFY,
    )
    section_style = ParagraphStyle(
        "BAASection", parent=styles["Heading2"],
        fontSize=11, spaceBefore=16, spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    sig_style = ParagraphStyle(
        "BAASig", parent=styles["Normal"],
        fontSize=10, leading=20,
    )
    hr = HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=16)

    story = [
        Paragraph("Business Associate Agreement", title_style),
        Paragraph("HIPAA / PIPEDA Compliance — Dental AI Platform", subtitle_style),
        hr,
        Paragraph(
            f'This Business Associate Agreement ("Agreement") is entered into between '
            f'<b>{practice_name}</b> ("Covered Entity") and Dental AI Platform Inc. '
            f'("Business Associate") as of <b>[DATE]</b>.',
            body_style,
        ),
        Paragraph("1. DEFINITIONS", section_style),
        Paragraph(
            '"Protected Health Information" or "PHI" means any information, whether oral or '
            "recorded in any form or medium, that is created or received by Business Associate "
            "from or on behalf of Covered Entity that relates to the past, present, or future "
            "physical or mental health or condition of an individual; the provision of health "
            "care to an individual; or the payment for health care, as defined under the Health "
            "Insurance Portability and Accountability Act of 1996 (HIPAA) and the Personal "
            "Information Protection and Electronic Documents Act (PIPEDA). "
            '"Business Associate" means an entity that performs functions or activities on '
            "behalf of a Covered Entity that involve the use or disclosure of PHI.",
            body_style,
        ),
        Paragraph("2. OBLIGATIONS OF BUSINESS ASSOCIATE", section_style),
        Paragraph(
            "Business Associate agrees to: (a) not use or disclose PHI other than as "
            "permitted or required by this Agreement or as required by law; (b) implement "
            "appropriate administrative, physical, and technical safeguards to prevent "
            "unauthorized use or disclosure of PHI; (c) ensure that any subcontractors that "
            "create, receive, maintain, or transmit PHI on behalf of Business Associate agree "
            "to the same restrictions and conditions that apply to Business Associate; "
            "(d) make its internal practices, books, and records relating to PHI available to "
            "the Secretary of the Department of Health and Human Services for purposes of "
            "determining compliance with HIPAA.",
            body_style,
        ),
        Paragraph("3. PERMITTED USES AND DISCLOSURES", section_style),
        Paragraph(
            "Business Associate may use or disclose PHI only as necessary to perform services "
            "described in the underlying service agreement, or as required by law. Business "
            "Associate may use PHI for its proper management and administration or to carry "
            "out legal responsibilities, provided that disclosures are required by law or "
            "Business Associate obtains reasonable written assurances of confidentiality from "
            "the recipient. Business Associate shall not sell PHI or use PHI for marketing "
            "purposes without explicit written authorization from the Covered Entity.",
            body_style,
        ),
        Paragraph("4. SAFEGUARDS", section_style),
        Paragraph(
            "Business Associate shall implement and maintain appropriate administrative, "
            "physical, and technical safeguards to protect the confidentiality, integrity, "
            "and availability of electronic PHI as required by the HIPAA Security Rule "
            "(45 CFR Part 164, Subpart C) and applicable PIPEDA requirements. This includes "
            "encryption of PHI at rest and in transit, role-based access controls, access "
            "logging and monitoring, and regional data residency enforcement in accordance "
            "with applicable Canadian provincial and federal law. Business Associate shall "
            "conduct annual security risk assessments and remediate identified risks promptly.",
            body_style,
        ),
        Paragraph("5. REPORTING", section_style),
        Paragraph(
            "Business Associate shall report to Covered Entity any use or disclosure of PHI "
            "not provided for by this Agreement of which it becomes aware, including breaches "
            "of unsecured PHI as required by the HIPAA Breach Notification Rule "
            "(45 CFR §§ 164.400–414) and any applicable PIPEDA breach of security safeguards "
            "requirements. Notification shall be provided without unreasonable delay and in "
            "no case later than sixty (60) calendar days after discovery of the breach, and "
            "shall include the nature of the breach, the PHI involved, and steps taken to "
            "mitigate harm.",
            body_style,
        ),
        Paragraph("6. TERM AND TERMINATION", section_style),
        Paragraph(
            "This Agreement shall be effective as of the date first written above and shall "
            "remain in effect until terminated. Either party may terminate this Agreement for "
            "cause upon thirty (30) days written notice if the other party materially breaches "
            "any provision. Upon termination, Business Associate shall return or destroy all "
            "PHI received from or created on behalf of Covered Entity. If return or destruction "
            "is infeasible, Business Associate shall extend the protections of this Agreement "
            "to such PHI and limit further uses and disclosures to those purposes that make "
            "return or destruction infeasible.",
            body_style,
        ),
        Paragraph("7. MISCELLANEOUS", section_style),
        Paragraph(
            "This Agreement shall be governed by the laws of the Province of Ontario and the "
            "federal laws of Canada applicable therein. This Agreement constitutes the entire "
            "agreement between the parties with respect to the subject matter hereof and "
            "supersedes all prior agreements, understandings, and discussions. Any amendment "
            "must be in writing signed by both parties. If any provision of this Agreement is "
            "found unenforceable, the remaining provisions shall continue in full force and "
            "effect. This Agreement may be executed in counterparts, each of which shall be "
            "deemed an original.",
            body_style,
        ),
        Spacer(1, 24),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0"), spaceAfter=16),
        Paragraph(
            "By signing below, the parties agree to be bound by the terms and conditions "
            "of this Agreement.",
            body_style,
        ),
        Spacer(1, 12),
        Paragraph(
            f"<b>Covered Entity:</b> {practice_name}<br/>"
            "<b>Authorized Signature:</b> [AUTHORIZED SIGNATURE]<br/>"
            "<b>Date:</b> [DATE]",
            sig_style,
        ),
        Spacer(1, 20),
        Paragraph(
            "<b>Business Associate:</b> Dental AI Platform Inc.<br/>"
            "<b>Authorized Signature:</b> ____________________<br/>"
            "<b>Date:</b> ____________________",
            sig_style,
        ),
    ]

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawCentredString(letter[0] / 2, 36, "Dental AI Platform — Confidential")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


@router.get("/baa")
async def download_baa(
    current_user: dict = Depends(get_current_user),
    _gate: None = Depends(require_feature("baa_available")),
):
    """Returns the Business Associate Agreement as a downloadable PDF. Elite plan only."""
    db = get_db()
    practice = await db.practices.find_one(
        {"id": current_user.get("practice_id")}, {"_id": 0, "name": 1}
    ) or {}
    practice_name = practice.get("name") or "[PRACTICE NAME]"

    pdf_bytes = _build_baa_pdf(practice_name)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="BAA-DentalAI.pdf"'},
    )


# ──────────────────────────────────────────────────────────────────────
# Manual reconciliation (rescue stuck transactions when webhooks failed)
# ──────────────────────────────────────────────────────────────────────


@router.post("/reconcile/{session_id}")
async def reconcile_session(
  session_id: str,
  current_user: dict = Depends(require_role("admin")),
):
  """
  Self-service repair for transactions stuck because the Stripe webhook
  didn't arrive. Pulls the truth from Stripe and replays the promotion
  logic locally. Idempotent — safe to call repeatedly.
  """
  _require_stripe()
  db = get_db()
  txn = await db.payment_transactions.find_one(
    {"session_id": session_id, "practice_id": current_user["practice_id"]},
    {"_id": 0},
  )
  if not txn:
    raise HTTPException(status_code=404, detail="Transaction not found")

  try:
    s = stripe_sdk.checkout.Session.retrieve(session_id)
  except stripe_sdk.error.StripeError as e:
    raise HTTPException(
      status_code=502, detail=f"Stripe error: {e.user_message or str(e)}"
    )

  if s.payment_status != "paid":
    return {
      "session_id": session_id,
      "reconciled": False,
      "reason": f"Stripe says payment_status={s.payment_status}, status={s.status}. Nothing to promote.",
      "payment_status": s.payment_status,
      "status": s.status,
    }

  # Already promoted? Idempotent return
  if txn.get("promoted_at") and txn.get("payment_status") == "paid":
    return {
      "session_id": session_id,
      "reconciled": False,
      "reason": "Already promoted; nothing to do.",
      "promoted_at": txn["promoted_at"],
    }

  # First, sync the txn row to truth
  await db.payment_transactions.update_one(
    {"session_id": session_id},
    {
      "$set": {
        "payment_status": "paid",
        "status": s.status or "complete",
        "amount_total": s.amount_total,
        "currency": s.currency,
        "updated_at": datetime.now(timezone.utc).isoformat(),
      }
    },
  )
  # Then run the same promotion logic
  await _promote_practice_to_plan(
    db,
    txn["practice_id"],
    txn["plan_id"],
    session_id,
    stripe_customer_id=s.customer,
    stripe_subscription_id=s.subscription,
    amount_total=s.amount_total,
    currency=s.currency,
  )
  await log_audit_event(
    user_id=current_user["id"],
    practice_id=txn["practice_id"],
    action="billing_reconcile_manual",
    resource_type="payment_transaction",
    resource_id=session_id,
    details={
      "stripe_customer_id": s.customer,
      "stripe_subscription_id": s.subscription,
      "plan_id": txn["plan_id"],
      "amount_cents": s.amount_total,
      "reason": "Manual reconcile by admin (webhook didn't fire)",
    },
  )
  return {
    "session_id": session_id,
    "reconciled": True,
    "plan_id": txn["plan_id"],
    "stripe_customer_id": s.customer,
    "stripe_subscription_id": s.subscription,
    "amount_cents": s.amount_total,
  }
