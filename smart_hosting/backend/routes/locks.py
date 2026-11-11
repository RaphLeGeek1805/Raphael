from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Property, Lock

locks_bp = Blueprint("locks", __name__)


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


def _owned_property(user_id: int, property_id: int):
    return Property.query.filter_by(id=property_id, user_id=user_id).first()


def _check_lock_limit(user: User, property_id: int) -> tuple[bool, str]:
    from flask import current_app
    limits = current_app.config["PLAN_LIMITS"].get(user.plan, {"locks_per_property": 2})
    max_locks = limits["locks_per_property"]
    if max_locks == -1:
        return True, ""
    current_count = Lock.query.filter_by(property_id=property_id).count()
    if current_count >= max_locks:
        return False, (
            f"Plan '{user.plan}' allows up to {max_locks} lock(s) per property. "
            "Upgrade to add more locks."
        )
    return True, ""


@locks_bp.route("/", methods=["GET"])
@jwt_required()
def list_locks():
    user = _get_current_user()
    property_id = request.args.get("property_id", type=int)

    # Collect IDs of properties owned by user
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    query = Lock.query.filter(Lock.property_id.in_(prop_ids))
    if property_id:
        if property_id not in prop_ids:
            return jsonify({"error": "Property not found or access denied"}), 404
        query = query.filter_by(property_id=property_id)

    locks = query.order_by(Lock.id.asc()).all()
    return jsonify({"locks": [lock.to_dict() for lock in locks]}), 200


@locks_bp.route("/", methods=["POST"])
@jwt_required()
def create_lock():
    user = _get_current_user()
    data = request.get_json(silent=True) or {}
    property_id = data.get("property_id")
    name = data.get("name", "").strip()

    if not property_id or not name:
        return jsonify({"error": "property_id and name are required"}), 400

    prop = _owned_property(user.id, property_id)
    if not prop:
        return jsonify({"error": "Property not found or access denied"}), 404

    allowed, err = _check_lock_limit(user, property_id)
    if not allowed:
        return jsonify({"error": err}), 403

    lock = Lock(
        property_id=property_id,
        name=name,
        model=data.get("model"),
        serial_number=data.get("serial_number"),
        provider=data.get("provider", "nuki"),
        external_lock_id=data.get("external_lock_id"),
        battery_level=data.get("battery_level", 100),
        status="offline",
    )
    db.session.add(lock)
    db.session.commit()
    return jsonify({"lock": lock.to_dict()}), 201


@locks_bp.route("/<int:lock_id>", methods=["GET"])
@jwt_required()
def get_lock(lock_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock = Lock.query.filter(Lock.id == lock_id, Lock.property_id.in_(prop_ids)).first_or_404()

    lock_data = lock.to_dict()
    # Include recent access codes history
    from models import AccessCode
    recent = (
        AccessCode.query.filter_by(lock_id=lock_id)
        .order_by(AccessCode.created_at.desc())
        .limit(20)
        .all()
    )
    lock_data["recent_codes"] = [c.to_dict() for c in recent]
    return jsonify({"lock": lock_data}), 200


@locks_bp.route("/<int:lock_id>", methods=["PUT"])
@jwt_required()
def update_lock(lock_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock = Lock.query.filter(Lock.id == lock_id, Lock.property_id.in_(prop_ids)).first_or_404()

    data = request.get_json(silent=True) or {}
    for field in ("name", "model", "serial_number", "provider", "external_lock_id", "battery_level", "status"):
        if field in data:
            setattr(lock, field, data[field])

    db.session.commit()
    return jsonify({"lock": lock.to_dict()}), 200


@locks_bp.route("/<int:lock_id>", methods=["DELETE"])
@jwt_required()
def delete_lock(lock_id):
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock = Lock.query.filter(Lock.id == lock_id, Lock.property_id.in_(prop_ids)).first_or_404()
    db.session.delete(lock)
    db.session.commit()
    return jsonify({"message": "Lock removed"}), 200


@locks_bp.route("/<int:lock_id>/sync", methods=["POST"])
@jwt_required()
def sync_lock(lock_id):
    """Simulate sync: query the lock provider for current status."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock = Lock.query.filter(Lock.id == lock_id, Lock.property_id.in_(prop_ids)).first_or_404()

    from services.lock_adapter import get_adapter
    adapter = get_adapter(lock.provider)
    result = adapter.get_status(lock.external_lock_id or str(lock_id))

    # Update lock state from adapter result
    lock.status = result.get("status", lock.status)
    lock.battery_level = result.get("battery_level", lock.battery_level)
    lock.last_seen_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()

    return jsonify({"lock": lock.to_dict(), "sync_result": result}), 200
