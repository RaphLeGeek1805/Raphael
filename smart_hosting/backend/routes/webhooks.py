"""
ACCESKEY Smart Hosting — Webhook endpoints
Handles incoming booking events from Airbnb, Booking.com and generic platforms.

POST /api/webhooks/airbnb
POST /api/webhooks/booking
POST /api/webhooks/generic
"""
import hashlib
import hmac
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from models import AccessCode, Booking, Lock, Property, db
from services.code_generator import generate_unique_code_for_lock, hash_code
from services.notification import send_access_code

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__)

# ---------------------------------------------------------------------------
# Helpers — HMAC signature verification
# ---------------------------------------------------------------------------


def _verify_hmac_signature(payload_bytes: bytes, header_name: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 webhook signature.
    Returns True if the signature matches or if no secret is configured.
    """
    if not secret:
        return True  # secret not configured → accept all (dev mode)

    signature_header = request.headers.get(header_name, "")
    if not signature_header:
        logger.warning("Webhook: missing signature header '%s'", header_name)
        return False

    # Support both raw hex and 'sha256=<hex>' formats
    expected_prefix = "sha256="
    if signature_header.startswith(expected_prefix):
        provided_sig = signature_header[len(expected_prefix):]
    else:
        provided_sig = signature_header

    computed = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, provided_sig)


# ---------------------------------------------------------------------------
# Helpers — property matching
# ---------------------------------------------------------------------------


def _find_property(platform: str, external_property_id: str = None) -> Property:
    """
    Try to find a matching Property row.

    Strategy:
      1. If external_property_id is provided, look for a Booking row that
         previously used it and return its property (best-effort).
      2. Fall back to the first active Property whose platform matches.
         (In production, add an `external_id` column to Property for exact matching.)

    Returns None if no match found.
    """
    if external_property_id:
        # Look for an existing booking on this external ID to infer the property
        existing = Booking.query.filter_by(
            external_booking_id=external_property_id
        ).first()
        if existing:
            return Property.query.get(existing.property_id)

        # Try platform-matching properties whose name/address contains the id
        # (last-resort heuristic — works when operator sets property name = listing id)
        prop = Property.query.filter(
            Property.platform.in_([platform, "both"]),
            Property.active.is_(True),
            Property.name.ilike(f"%{external_property_id}%"),
        ).first()
        if prop:
            return prop

    # Broadest fallback: first active property accepting this platform
    prop = Property.query.filter(
        Property.platform.in_([platform, "both"]),
        Property.active.is_(True),
    ).first()
    return prop


# ---------------------------------------------------------------------------
# Helpers — booking upsert
# ---------------------------------------------------------------------------


def _upsert_booking(
    *,
    property_obj: Property,
    platform: str,
    external_booking_id: str,
    guest_name: str,
    guest_email: str = None,
    guest_phone: str = None,
    check_in: datetime,
    check_out: datetime,
) -> tuple[Booking, bool]:
    """
    Insert or update a Booking row.
    Returns (booking, created) where created is True for new rows.
    """
    booking = Booking.query.filter_by(
        external_booking_id=external_booking_id
    ).first()

    if booking:
        # Update mutable fields
        booking.guest_name = guest_name
        booking.guest_email = guest_email or booking.guest_email
        booking.guest_phone = guest_phone or booking.guest_phone
        booking.check_in = check_in
        booking.check_out = check_out
        booking.status = "upcoming" if check_in > datetime.utcnow() else booking.status
        db.session.commit()
        logger.info("Webhook: updated existing booking %s", external_booking_id)
        return booking, False

    booking = Booking(
        property_id=property_obj.id,
        platform=platform,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_phone=guest_phone,
        check_in=check_in,
        check_out=check_out,
        status="upcoming",
        access_code_sent=False,
        external_booking_id=external_booking_id,
    )
    db.session.add(booking)
    db.session.commit()
    logger.info("Webhook: created new booking %s", external_booking_id)
    return booking, True


# ---------------------------------------------------------------------------
# Helpers — access code generation + notification
# ---------------------------------------------------------------------------


def _generate_and_send_codes(app, booking_id: int) -> None:
    """
    Generate one AccessCode per active Lock on the booking's property,
    then notify the guest.  Runs inside the app context (safe for threads).
    """
    with app.app_context():
        booking = Booking.query.get(booking_id)
        if not booking:
            logger.error("Webhook scheduler: booking %s not found", booking_id)
            return

        if booking.access_code_sent:
            logger.info("Webhook scheduler: codes already sent for booking %s", booking_id)
            return

        prop = Property.query.get(booking.property_id)
        locks = Lock.query.filter_by(property_id=prop.id, status="online").all()
        if not locks:
            locks = Lock.query.filter_by(property_id=prop.id).all()

        if not locks:
            logger.warning(
                "Webhook: property %s has no locks — cannot generate codes for booking %s",
                prop.id, booking_id,
            )
            return

        valid_from = booking.check_in
        valid_until = booking.check_out + timedelta(hours=2)

        generated_codes = []
        for lock in locks:
            try:
                code_val = generate_unique_code_for_lock(
                    lock.id, valid_from, valid_until
                )
                access_code = AccessCode(
                    lock_id=lock.id,
                    booking_id=booking.id,
                    code_hash=hash_code(code_val),
                    code_display=code_val,
                    guest_name=booking.guest_name,
                    guest_email=booking.guest_email,
                    guest_phone=booking.guest_phone,
                    valid_from=valid_from,
                    valid_until=valid_until,
                    status="active",
                )
                db.session.add(access_code)
                generated_codes.append((lock.name, code_val))
                logger.info(
                    "Webhook: generated code %s for lock '%s' (booking %s)",
                    code_val, lock.name, booking_id,
                )
            except ValueError as exc:
                logger.error(
                    "Webhook: could not generate code for lock %s: %s", lock.id, exc
                )

        if generated_codes:
            # Use the first code in the notification (main door)
            primary_code = generated_codes[0][1]
            send_access_code(
                guest_name=booking.guest_name,
                guest_phone=booking.guest_phone,
                guest_email=booking.guest_email,
                code=primary_code,
                valid_from=valid_from,
                valid_until=valid_until,
                property_name=prop.name,
            )
            booking.access_code_sent = True
            db.session.commit()
            logger.info(
                "Webhook: access code sent to guest '%s' for booking %s",
                booking.guest_name, booking_id,
            )


def _schedule_or_send_now(app, booking: Booking) -> str:
    """
    If check-in is within 48 hours → generate codes immediately.
    Otherwise → schedule generation for J-1 (via a background thread with sleep).
    Returns a human-readable action string for logging.
    """
    now = datetime.utcnow()
    hours_until_checkin = (booking.check_in - now).total_seconds() / 3600

    if hours_until_checkin <= 48:
        # Immediate generation in background thread
        t = threading.Thread(
            target=_generate_and_send_codes,
            args=(app, booking.id),
            daemon=True,
        )
        t.start()
        return "immediate"

    # Schedule for J-1 00:00 of check-in
    day_before = booking.check_in - timedelta(days=1)
    day_before = day_before.replace(hour=10, minute=0, second=0, microsecond=0)
    delay_seconds = max((day_before - now).total_seconds(), 0)

    def _delayed_generate():
        time.sleep(delay_seconds)
        _generate_and_send_codes(app, booking.id)

    t = threading.Thread(target=_delayed_generate, daemon=True)
    t.start()
    return f"scheduled_for_{day_before.isoformat()}"


# ---------------------------------------------------------------------------
# Shared processing entry point
# ---------------------------------------------------------------------------


def _process_webhook(
    *,
    platform: str,
    event: str,
    external_booking_id: str,
    external_property_id: str = None,
    guest_name: str,
    guest_email: str = None,
    guest_phone: str = None,
    check_in_str: str,
    check_out_str: str,
) -> tuple[dict, int]:
    """
    Core processing shared by all three webhook endpoints.
    Returns (response_dict, http_status).
    """
    # Parse dates
    try:
        check_in = datetime.strptime(check_in_str, "%Y-%m-%d")
        check_out = datetime.strptime(check_out_str, "%Y-%m-%d")
    except (ValueError, TypeError) as exc:
        logger.warning("Webhook: invalid date format — %s", exc)
        return {"status": "ignored", "reason": "invalid_date_format"}, 200

    # Ignore cancellations / non-new events
    ignorable_events = {
        "reservation.cancelled",
        "reservation.rejected",
        "booking.cancelled",
        "booking.modified",
    }
    if event in ignorable_events:
        logger.info("Webhook: ignoring event '%s' for %s", event, external_booking_id)
        return {"status": "ignored", "reason": "event_not_actionable"}, 200

    # Find property
    prop = _find_property(platform, external_property_id)
    if prop is None:
        logger.warning(
            "Webhook: no matching property found for platform='%s' "
            "external_property_id='%s' — ignoring gracefully",
            platform, external_property_id,
        )
        return {"status": "accepted", "reason": "property_not_found"}, 200

    # Upsert booking
    booking, created = _upsert_booking(
        property_obj=prop,
        platform=platform,
        external_booking_id=external_booking_id,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_phone=guest_phone,
        check_in=check_in,
        check_out=check_out,
    )

    # Generate/schedule codes only on create (or if codes not yet sent on update)
    action = "skipped"
    if created or not booking.access_code_sent:
        app = current_app._get_current_object()  # safe reference for threads
        action = _schedule_or_send_now(app, booking)

    return {
        "status": "ok",
        "booking_id": booking.id,
        "created": created,
        "code_action": action,
    }, 200


# ---------------------------------------------------------------------------
# Airbnb webhook
# ---------------------------------------------------------------------------


@webhooks_bp.route("/airbnb", methods=["POST"])
def webhook_airbnb():
    """
    Handle Airbnb reservation events.

    Expected payload:
    {
        "event": "reservation.created",
        "reservation": {
            "confirmation_code": "HMABCD123",
            "guest": {
                "first_name": "Thomas",
                "last_name": "Martin",
                "email": "thomas@example.com",
                "phone": "+33612345678"
            },
            "listing_id": "12345678",
            "check_in": "2024-02-15",
            "check_out": "2024-02-19",
            "status": "accepted"
        }
    }
    """
    payload_bytes = request.get_data()
    secret = current_app.config.get("AIRBNB_WEBHOOK_SECRET", "")

    if not _verify_hmac_signature(payload_bytes, "X-Airbnb-Signature", secret):
        logger.warning("Airbnb webhook: invalid HMAC signature")
        return jsonify({"error": "Invalid signature"}), 403

    data = request.get_json(silent=True) or {}
    event = data.get("event", "")
    reservation = data.get("reservation", {})

    if not reservation:
        return jsonify({"status": "ignored", "reason": "missing_reservation"}), 200

    guest = reservation.get("guest", {})
    guest_name = " ".join(
        filter(None, [guest.get("first_name", ""), guest.get("last_name", "")])
    ).strip() or "Guest"

    result, status = _process_webhook(
        platform="airbnb",
        event=event,
        external_booking_id=reservation.get("confirmation_code", ""),
        external_property_id=str(reservation.get("listing_id", "")),
        guest_name=guest_name,
        guest_email=guest.get("email"),
        guest_phone=guest.get("phone"),
        check_in_str=reservation.get("check_in", ""),
        check_out_str=reservation.get("check_out", ""),
    )
    return jsonify(result), status


# ---------------------------------------------------------------------------
# Booking.com webhook
# ---------------------------------------------------------------------------


@webhooks_bp.route("/booking", methods=["POST"])
def webhook_booking():
    """
    Handle Booking.com reservation events.

    Expected payload:
    {
        "event": "booking.new",
        "booking_id": "BK98765",
        "property_id": "PROP001",
        "guest_name": "Marie Dupont",
        "guest_email": "marie@example.com",
        "guest_phone": "+33698765432",
        "arrival": "2024-02-20",
        "departure": "2024-02-25"
    }
    """
    payload_bytes = request.get_data()
    secret = current_app.config.get("BOOKING_WEBHOOK_SECRET", "")

    if not _verify_hmac_signature(payload_bytes, "X-Booking-Signature", secret):
        logger.warning("Booking.com webhook: invalid HMAC signature")
        return jsonify({"error": "Invalid signature"}), 403

    data = request.get_json(silent=True) or {}

    result, status = _process_webhook(
        platform="booking",
        event=data.get("event", "booking.new"),
        external_booking_id=str(data.get("booking_id", "")),
        external_property_id=str(data.get("property_id", "")),
        guest_name=data.get("guest_name", "Guest"),
        guest_email=data.get("guest_email"),
        guest_phone=data.get("guest_phone"),
        check_in_str=data.get("arrival", ""),
        check_out_str=data.get("departure", ""),
    )
    return jsonify(result), status


# ---------------------------------------------------------------------------
# Generic / universal webhook
# ---------------------------------------------------------------------------


@webhooks_bp.route("/generic", methods=["POST"])
def webhook_generic():
    """
    Handle generic booking events from any platform (Abritel, Vrbo, direct, …).

    Expected payload:
    {
        "platform": "abritel",
        "event": "new_booking",
        "external_id": "AB001",
        "property_external_id": "P001",
        "guest": {
            "name": "Sophie Leclerc",
            "email": "sophie@example.com",
            "phone": "+33756789012"
        },
        "check_in": "2024-03-10",
        "check_out": "2024-03-15"
    }
    """
    payload_bytes = request.get_data()
    # Generic webhooks use a single shared secret (BOOKING_WEBHOOK_SECRET as fallback)
    secret = current_app.config.get("GENERIC_WEBHOOK_SECRET", "") or current_app.config.get(
        "BOOKING_WEBHOOK_SECRET", ""
    )

    if not _verify_hmac_signature(payload_bytes, "X-Webhook-Signature", secret):
        logger.warning("Generic webhook: invalid HMAC signature")
        return jsonify({"error": "Invalid signature"}), 403

    data = request.get_json(silent=True) or {}
    guest = data.get("guest", {})

    platform = data.get("platform", "other")

    result, status = _process_webhook(
        platform=platform,
        event=data.get("event", "new_booking"),
        external_booking_id=str(data.get("external_id", "")),
        external_property_id=str(data.get("property_external_id", "")),
        guest_name=guest.get("name", "Guest"),
        guest_email=guest.get("email"),
        guest_phone=guest.get("phone"),
        check_in_str=data.get("check_in", ""),
        check_out_str=data.get("check_out", ""),
    )
    return jsonify(result), status
