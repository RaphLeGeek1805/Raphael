"""
Billing routes — Stripe Checkout, Webhooks, Customer Portal, Status.

All routes that call Stripe are guarded: if STRIPE_SECRET_KEY is not set
the endpoint returns a mock/stub response so local dev works without keys.
"""
import logging
from datetime import datetime, timedelta, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, User, StripeCustomer

logger = logging.getLogger(__name__)

billing_bp = Blueprint("billing", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stripe():
    """Return a configured stripe module, or None if key is missing."""
    key = current_app.config.get("STRIPE_SECRET_KEY", "")
    if not key:
        return None
    import stripe as _stripe_lib
    _stripe_lib.api_key = key
    return _stripe_lib


def _mock_response(message: str, data: dict):
    """Return a stub JSON response used when Stripe is not configured."""
    return jsonify({"mock": True, "message": message, **data}), 200


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_or_create_stripe_customer(stripe, user: User) -> str:
    """Return (or lazily create) the Stripe customer ID for a user."""
    sc = StripeCustomer.query.filter_by(user_id=user.id).first()
    if sc:
        return sc.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=user.name,
        metadata={"user_id": str(user.id)},
    )
    sc = StripeCustomer(
        user_id=user.id,
        stripe_customer_id=customer["id"],
    )
    db.session.add(sc)
    db.session.commit()
    return customer["id"]


# ---------------------------------------------------------------------------
# POST /api/billing/create-checkout-session
# ---------------------------------------------------------------------------

@billing_bp.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """
    Body: { plan: "starter"|"pro"|"business", email: "..." }
    Returns: { checkout_url: "https://checkout.stripe.com/..." }
    """
    data = request.get_json(silent=True) or {}
    plan = data.get("plan", "").lower()
    email = data.get("email", "").strip().lower()

    valid_plans = ("starter", "pro", "business")
    if plan not in valid_plans:
        return jsonify({"error": f"plan must be one of {valid_plans}"}), 400
    if not email:
        return jsonify({"error": "email is required"}), 400

    stripe = _stripe()
    if stripe is None:
        return _mock_response(
            "Stripe not configured — returning mock checkout URL",
            {"checkout_url": f"https://checkout.stripe.com/mock?plan={plan}&email={email}"},
        )

    price_ids = current_app.config["STRIPE_PRICE_IDS"]
    price_id = price_ids.get(plan)
    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000")

    # Resolve an existing Stripe customer by email if the user exists
    user = User.query.filter_by(email=email).first()
    customer_id = None
    if user:
        try:
            customer_id = _get_or_create_stripe_customer(stripe, user)
        except Exception as exc:
            logger.warning("Could not resolve Stripe customer: %s", exc)

    session_kwargs = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{frontend_url}/billing/cancel",
        "subscription_data": {
            "trial_period_days": current_app.config.get("TRIAL_DAYS", 14),
            "metadata": {"plan": plan, "user_email": email},
        },
        "metadata": {"plan": plan, "user_email": email},
    }
    if customer_id:
        session_kwargs["customer"] = customer_id
    else:
        session_kwargs["customer_email"] = email

    try:
        checkout_session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.error.StripeError as exc:
        logger.error("Stripe error creating checkout session: %s", exc)
        return jsonify({"error": str(exc.user_message or exc)}), 502

    return jsonify({"checkout_url": checkout_session["url"]}), 200


# ---------------------------------------------------------------------------
# POST /api/billing/webhook
# ---------------------------------------------------------------------------

@billing_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Stripe webhook endpoint.
    Handles:
      - checkout.session.completed  → upgrade user plan
      - customer.subscription.deleted → downgrade to free
      - invoice.payment_failed → stub notification
    """
    stripe = _stripe()
    webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET", "")

    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    if stripe is None:
        # Dev mode: accept raw JSON without signature verification
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return jsonify({"error": "Invalid JSON"}), 400
    else:
        if not webhook_secret:
            return jsonify({"error": "Webhook secret not configured"}), 500
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError as exc:
            logger.warning("Webhook signature verification failed: %s", exc)
            return jsonify({"error": "Invalid signature"}), 400
        except Exception as exc:
            logger.error("Webhook construct_event error: %s", exc)
            return jsonify({"error": "Webhook error"}), 400

    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    event_data = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(event_data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(event_data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(event_data)

    return jsonify({"received": True}), 200


def _handle_checkout_completed(session):
    """Upgrade user plan after successful checkout."""
    metadata = session.get("metadata") or {}
    plan = metadata.get("plan", "starter")
    user_email = metadata.get("user_email", "")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    user = User.query.filter_by(email=user_email).first()
    if not user and customer_id:
        # Try via StripeCustomer record
        sc = StripeCustomer.query.filter_by(stripe_customer_id=customer_id).first()
        if sc:
            user = User.query.get(sc.user_id)

    if not user:
        logger.warning("checkout.session.completed: no user found for email=%s customer=%s", user_email, customer_id)
        return

    # Upgrade plan — no expiry (subscription handles it)
    user.plan = plan
    user.plan_expires_at = None

    # Keep StripeCustomer in sync
    sc = StripeCustomer.query.filter_by(user_id=user.id).first()
    if sc is None:
        sc = StripeCustomer(user_id=user.id, stripe_customer_id=customer_id)
        db.session.add(sc)
    else:
        sc.stripe_customer_id = customer_id or sc.stripe_customer_id
    if subscription_id:
        sc.stripe_subscription_id = subscription_id

    db.session.commit()
    logger.info("User %s upgraded to plan=%s", user.email, plan)


def _handle_subscription_deleted(subscription):
    """Downgrade user to free when subscription is cancelled."""
    customer_id = subscription.get("customer")
    sc = StripeCustomer.query.filter_by(stripe_customer_id=customer_id).first()
    if not sc:
        logger.warning("subscription.deleted: no StripeCustomer for customer_id=%s", customer_id)
        return

    user = User.query.get(sc.user_id)
    if not user:
        return

    user.plan = "free"
    user.plan_expires_at = None
    sc.stripe_subscription_id = None
    db.session.commit()
    logger.info("User %s downgraded to free (subscription deleted)", user.email)


def _handle_payment_failed(invoice):
    """Stub: send payment failure notification email."""
    customer_id = invoice.get("customer")
    sc = StripeCustomer.query.filter_by(stripe_customer_id=customer_id).first()
    email = invoice.get("customer_email", "")

    if sc:
        user = User.query.get(sc.user_id)
        email = email or (user.email if user else "")

    logger.warning("invoice.payment_failed for customer=%s email=%s — sending retry notification (stub)", customer_id, email)
    # Stub: replace with real email send via services/notification.py when SMTP is configured
    _stub_send_payment_failed_email(email)


def _stub_send_payment_failed_email(email: str):
    """Stub notification — logs the intent; wire up real SMTP when ready."""
    logger.info("[STUB] Payment failed email → %s : 'Your payment failed, please update your payment method.'", email)


# ---------------------------------------------------------------------------
# GET /api/billing/portal
# ---------------------------------------------------------------------------

@billing_bp.route("/portal", methods=["GET"])
@jwt_required()
def portal():
    """
    Returns a Stripe Customer Portal URL so the user can manage their subscription.
    Requires JWT auth.
    """
    user_id = int(get_jwt_identity())
    user = User.query.get_or_404(user_id)

    stripe = _stripe()
    if stripe is None:
        return _mock_response(
            "Stripe not configured — returning mock portal URL",
            {"portal_url": f"https://billing.stripe.com/mock?customer=mock_{user.email}"},
        )

    frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:3000")

    try:
        customer_id = _get_or_create_stripe_customer(stripe, user)
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{frontend_url}/dashboard",
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe error creating portal session: %s", exc)
        return jsonify({"error": str(exc.user_message or exc)}), 502

    return jsonify({"portal_url": portal_session["url"]}), 200


# ---------------------------------------------------------------------------
# GET /api/billing/status
# ---------------------------------------------------------------------------

@billing_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    """
    Returns the current billing status of the authenticated user.
    Response:
    {
        plan: "starter"|"pro"|"business"|"free",
        plan_expires_at: "ISO8601 or null",
        trial_active: bool,
        trial_days_remaining: int|null,
        stripe_customer_id: str|null,
        stripe_subscription_id: str|null
    }
    """
    user_id = int(get_jwt_identity())
    user = User.query.get_or_404(user_id)

    now = _utcnow()
    trial_active = False
    trial_days_remaining = None

    if user.plan_expires_at and user.plan_expires_at > now:
        # plan_expires_at is set during trial period
        delta = user.plan_expires_at - now
        trial_active = True
        trial_days_remaining = max(0, delta.days)

    sc = StripeCustomer.query.filter_by(user_id=user.id).first()

    return jsonify({
        "plan": user.plan,
        "plan_expires_at": user.plan_expires_at.isoformat() if user.plan_expires_at else None,
        "trial_active": trial_active,
        "trial_days_remaining": trial_days_remaining,
        "stripe_customer_id": sc.stripe_customer_id if sc else None,
        "stripe_subscription_id": sc.stripe_subscription_id if sc else None,
    }), 200
