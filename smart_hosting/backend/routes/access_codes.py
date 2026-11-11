from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Property, Lock, AccessCode, Booking
from services.code_generator import generate_unique_code_for_lock, hash_code

codes_bp = Blueprint("codes", __name__)


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


def _owned_lock(user: User, lock_id: int):
    """Return Lock if it belongs to the user, else None."""
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    return Lock.query.filter(Lock.id == lock_id, Lock.property_id.in_(prop_ids)).first()


@codes_bp.route("/", methods=["GET"])
@jwt_required()
def list_codes():
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]

    query = AccessCode.query.filter(AccessCode.lock_id.in_(lock_ids))

    # Filters
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)

    property_id = request.args.get("property_id", type=int)
    if property_id:
        filtered_lock_ids = [l.id for l in Lock.query.filter_by(property_id=property_id).all()]
        query = query.filter(AccessCode.lock_id.in_(filtered_lock_ids))

    codes = query.order_by(AccessCode.created_at.desc()).limit(100).all()
    return jsonify({"codes": [c.to_dict() for c in codes]}), 200


@codes_bp.route("/", methods=["POST"])
@jwt_required()
def create_code_manual():
    """Manually generate an access code for a lock."""
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    lock_id = data.get("lock_id")
    guest_name = data.get("guest_name", "").strip()
    valid_from_str = data.get("valid_from")
    valid_until_str = data.get("valid_until")

    if not all([lock_id, guest_name, valid_from_str, valid_until_str]):
        return jsonify({"error": "lock_id, guest_name, valid_from and valid_until are required"}), 400

    lock = _owned_lock(user, lock_id)
    if not lock:
        return jsonify({"error": "Lock not found or access denied"}), 404

    try:
        valid_from = datetime.fromisoformat(valid_from_str)
        valid_until = datetime.fromisoformat(valid_until_str)
    except ValueError:
        return jsonify({"error": "valid_from and valid_until must be ISO 8601 datetime strings"}), 400

    if valid_from >= valid_until:
        return jsonify({"error": "valid_from must be before valid_until"}), 400

    try:
        code = generate_unique_code_for_lock(lock_id, valid_from, valid_until)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409

    access_code = AccessCode(
        lock_id=lock_id,
        code_hash=hash_code(code),
        code_display=code,
        guest_name=guest_name,
        guest_email=data.get("guest_email"),
        guest_phone=data.get("guest_phone"),
        valid_from=valid_from,
        valid_until=valid_until,
        status="active",
    )
    db.session.add(access_code)

    # Push to lock adapter
    from services.lock_adapter import get_adapter
    adapter = get_adapter(lock.provider)
    adapter.set_code(lock.external_lock_id or str(lock_id), code, valid_from, valid_until)

    db.session.commit()
    result = access_code.to_dict(show_code=True)
    return jsonify({"code": result}), 201


@codes_bp.route("/auto", methods=["POST"])
@jwt_required()
def create_code_auto():
    """Automatically generate a code for an existing booking."""
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    booking_id = data.get("booking_id")
    lock_id = data.get("lock_id")

    if not booking_id or not lock_id:
        return jsonify({"error": "booking_id and lock_id are required"}), 400

    # Verify booking belongs to user
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    booking = Booking.query.filter(
        Booking.id == booking_id, Booking.property_id.in_(prop_ids)
    ).first()
    if not booking:
        return jsonify({"error": "Booking not found or access denied"}), 404

    lock = _owned_lock(user, lock_id)
    if not lock:
        return jsonify({"error": "Lock not found or access denied"}), 404

    # Extend validity slightly (check-in day 15:00 → check-out day 12:00 by default)
    valid_from = booking.check_in
    valid_until = booking.check_out

    try:
        code = generate_unique_code_for_lock(lock_id, valid_from, valid_until)
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
        valid_from=valid_from,
        valid_until=valid_until,
        status="active",
    )
    db.session.add(access_code)

    from services.lock_adapter import get_adapter
    adapter = get_adapter(lock.provider)
    adapter.set_code(lock.external_lock_id or str(lock_id), code, valid_from, valid_until)

    db.session.commit()
    result = access_code.to_dict(show_code=True)
    return jsonify({"code": result}), 201


@codes_bp.route("/<int:code_id>", methods=["GET"])
@jwt_required()
def get_code(code_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]
    code = AccessCode.query.filter(
        AccessCode.id == code_id, AccessCode.lock_id.in_(lock_ids)
    ).first_or_404()
    return jsonify({"code": code.to_dict(show_code=True)}), 200


@codes_bp.route("/<int:code_id>", methods=["DELETE"])
@jwt_required()
def revoke_code(code_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]
    access_code = AccessCode.query.filter(
        AccessCode.id == code_id, AccessCode.lock_id.in_(lock_ids)
    ).first_or_404()

    if access_code.status == "revoked":
        return jsonify({"error": "Code already revoked"}), 400

    # Revoke on the lock adapter
    lock = Lock.query.get(access_code.lock_id)
    from services.lock_adapter import get_adapter
    adapter = get_adapter(lock.provider)
    adapter.revoke_code(lock.external_lock_id or str(lock.id), access_code.code_display)

    access_code.status = "revoked"
    db.session.commit()
    return jsonify({"message": "Code revoked", "code": access_code.to_dict()}), 200


@codes_bp.route("/<int:code_id>/send", methods=["POST"])
@jwt_required()
def send_code(code_id):
    """Send the access code to the guest via SMS/email."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]
    access_code = AccessCode.query.filter(
        AccessCode.id == code_id, AccessCode.lock_id.in_(lock_ids)
    ).first_or_404()

    if access_code.status != "active":
        return jsonify({"error": "Cannot send a non-active code"}), 400

    lock = Lock.query.get(access_code.lock_id)
    prop = Property.query.get(lock.property_id)

    from services.notification import send_access_code
    result = send_access_code(
        guest_name=access_code.guest_name,
        guest_phone=access_code.guest_phone,
        guest_email=access_code.guest_email,
        code=access_code.code_display,
        valid_from=access_code.valid_from,
        valid_until=access_code.valid_until,
        property_name=prop.name,
    )
    return jsonify({"message": "Notification sent", "result": result}), 200
