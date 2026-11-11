from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Property, Lock, Booking, AccessCode
from services.code_generator import generate_unique_code_for_lock, hash_code

bookings_bp = Blueprint("bookings", __name__)


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


def _update_booking_statuses():
    """Auto-update booking statuses based on current date."""
    now = datetime.utcnow()
    # active: check_in <= now <= check_out
    Booking.query.filter(
        Booking.status == "upcoming",
        Booking.check_in <= now,
        Booking.check_out >= now,
    ).update({"status": "active"}, synchronize_session=False)
    # completed
    Booking.query.filter(
        Booking.status.in_(["upcoming", "active"]),
        Booking.check_out < now,
    ).update({"status": "completed"}, synchronize_session=False)
    db.session.commit()


@bookings_bp.route("/", methods=["GET"])
@jwt_required()
def list_bookings():
    user = _get_current_user()
    _update_booking_statuses()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    query = Booking.query.filter(Booking.property_id.in_(prop_ids))

    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    property_id = request.args.get("property_id", type=int)
    if property_id:
        query = query.filter_by(property_id=property_id)

    bookings = query.order_by(Booking.check_in.desc()).all()
    return jsonify({"bookings": [b.to_dict() for b in bookings]}), 200


@bookings_bp.route("/", methods=["POST"])
@jwt_required()
def create_booking():
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    property_id = data.get("property_id")
    guest_name = data.get("guest_name", "").strip()
    check_in_str = data.get("check_in")
    check_out_str = data.get("check_out")

    if not all([property_id, guest_name, check_in_str, check_out_str]):
        return jsonify({"error": "property_id, guest_name, check_in and check_out are required"}), 400

    prop = Property.query.filter_by(id=property_id, user_id=user.id).first()
    if not prop:
        return jsonify({"error": "Property not found or access denied"}), 404

    try:
        check_in = datetime.fromisoformat(check_in_str)
        check_out = datetime.fromisoformat(check_out_str)
    except ValueError:
        return jsonify({"error": "check_in and check_out must be ISO 8601 datetime strings"}), 400

    if check_in >= check_out:
        return jsonify({"error": "check_in must be before check_out"}), 400

    now = datetime.utcnow()
    if check_in > now:
        status = "upcoming"
    elif check_out < now:
        status = "completed"
    else:
        status = "active"

    booking = Booking(
        property_id=property_id,
        platform=data.get("platform", "airbnb"),
        guest_name=guest_name,
        guest_email=data.get("guest_email"),
        guest_phone=data.get("guest_phone"),
        check_in=check_in,
        check_out=check_out,
        status=status,
        external_booking_id=data.get("external_booking_id"),
    )
    db.session.add(booking)
    db.session.commit()
    return jsonify({"booking": booking.to_dict()}), 201


@bookings_bp.route("/<int:booking_id>", methods=["GET"])
@jwt_required()
def get_booking(booking_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    booking = Booking.query.filter(
        Booking.id == booking_id, Booking.property_id.in_(prop_ids)
    ).first_or_404()
    data = booking.to_dict()
    data["access_codes"] = [c.to_dict() for c in booking.access_codes.all()]
    return jsonify({"booking": data}), 200


@bookings_bp.route("/<int:booking_id>", methods=["PUT"])
@jwt_required()
def update_booking(booking_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    booking = Booking.query.filter(
        Booking.id == booking_id, Booking.property_id.in_(prop_ids)
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    for field in ("platform", "guest_name", "guest_email", "guest_phone", "status",
                  "access_code_sent", "external_booking_id"):
        if field in data:
            setattr(booking, field, data[field])

    if "check_in" in data:
        booking.check_in = datetime.fromisoformat(data["check_in"])
    if "check_out" in data:
        booking.check_out = datetime.fromisoformat(data["check_out"])

    db.session.commit()
    return jsonify({"booking": booking.to_dict()}), 200


@bookings_bp.route("/<int:booking_id>/generate-code", methods=["POST"])
@jwt_required()
def generate_code_for_booking(booking_id):
    """Generate and optionally send an access code for a booking."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    booking = Booking.query.filter(
        Booking.id == booking_id, Booking.property_id.in_(prop_ids)
    ).first_or_404()

    data = request.get_json(silent=True) or {}
    lock_id = data.get("lock_id")
    send_notification = data.get("send_notification", True)

    if not lock_id:
        # Auto-pick first lock on the property
        lock = Lock.query.filter_by(property_id=booking.property_id).first()
        if not lock:
            return jsonify({"error": "No lock found on this property"}), 404
        lock_id = lock.id
    else:
        lock = Lock.query.filter_by(id=lock_id, property_id=booking.property_id).first()
        if not lock:
            return jsonify({"error": "Lock not found on this property"}), 404

    try:
        code = generate_unique_code_for_lock(lock_id, booking.check_in, booking.check_out)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    access_code = AccessCode(
        lock_id=lock_id,
        booking_id=booking_id,
        code_hash=hash_code(code),
        code_display=code,
        guest_name=booking.guest_name,
        guest_email=booking.guest_email,
        guest_phone=booking.guest_phone,
        valid_from=booking.check_in,
        valid_until=booking.check_out,
        status="active",
    )
    db.session.add(access_code)

    from services.lock_adapter import get_adapter
    adapter = get_adapter(lock.provider)
    adapter.set_code(lock.external_lock_id or str(lock_id), code, booking.check_in, booking.check_out)

    notification_result = {}
    if send_notification and (booking.guest_email or booking.guest_phone):
        from services.notification import send_access_code
        prop = Property.query.get(booking.property_id)
        notification_result = send_access_code(
            guest_name=booking.guest_name,
            guest_phone=booking.guest_phone,
            guest_email=booking.guest_email,
            code=code,
            valid_from=booking.check_in,
            valid_until=booking.check_out,
            property_name=prop.name,
        )
        booking.access_code_sent = True

    db.session.commit()
    return jsonify({
        "code": access_code.to_dict(show_code=True),
        "notification": notification_result,
    }), 201
