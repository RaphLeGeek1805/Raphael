from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Property

properties_bp = Blueprint("properties", __name__)


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


def _check_plan_limit(user: User) -> tuple[bool, str]:
    """Return (allowed, error_message)."""
    limits = user._get_plan_limits()
    max_props = limits["properties"]
    if max_props == -1:
        return True, ""
    current_count = Property.query.filter_by(user_id=user.id).count()
    if current_count >= max_props:
        return False, (
            f"Plan '{user.plan}' allows up to {max_props} property/properties. "
            "Upgrade your plan to add more."
        )
    return True, ""


# Monkey-patch plan limit helper onto User at import time (avoids circular import)
def _get_plan_limits(self):
    from flask import current_app
    return current_app.config["PLAN_LIMITS"].get(self.plan, {"properties": 1, "locks_per_property": 2})

User._get_plan_limits = _get_plan_limits


@properties_bp.route("/", methods=["GET"])
@jwt_required()
def list_properties():
    user = _get_current_user()
    props = Property.query.filter_by(user_id=user.id).order_by(Property.created_at.desc()).all()
    return jsonify({"properties": [p.to_dict() for p in props]}), 200


@properties_bp.route("/", methods=["POST"])
@jwt_required()
def create_property():
    user = _get_current_user()
    allowed, err = _check_plan_limit(user)
    if not allowed:
        return jsonify({"error": err}), 403

    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    address = data.get("address", "").strip()
    city = data.get("city", "").strip()

    if not name or not address or not city:
        return jsonify({"error": "name, address and city are required"}), 400

    prop = Property(
        user_id=user.id,
        name=name,
        address=address,
        city=city,
        type=data.get("type", "apartment"),
        platform=data.get("platform", "airbnb"),
        active=data.get("active", True),
    )
    db.session.add(prop)
    db.session.commit()
    return jsonify({"property": prop.to_dict()}), 201


@properties_bp.route("/<int:prop_id>", methods=["GET"])
@jwt_required()
def get_property(prop_id):
    user = _get_current_user()
    prop = Property.query.filter_by(id=prop_id, user_id=user.id).first_or_404()
    return jsonify({"property": prop.to_dict(include_locks=True)}), 200


@properties_bp.route("/<int:prop_id>", methods=["PUT"])
@jwt_required()
def update_property(prop_id):
    user = _get_current_user()
    prop = Property.query.filter_by(id=prop_id, user_id=user.id).first_or_404()

    data = request.get_json(silent=True) or {}
    for field in ("name", "address", "city", "type", "platform", "active"):
        if field in data:
            setattr(prop, field, data[field])

    db.session.commit()
    return jsonify({"property": prop.to_dict()}), 200


@properties_bp.route("/<int:prop_id>", methods=["DELETE"])
@jwt_required()
def delete_property(prop_id):
    user = _get_current_user()
    prop = Property.query.filter_by(id=prop_id, user_id=user.id).first_or_404()
    db.session.delete(prop)
    db.session.commit()
    return jsonify({"message": "Property deleted"}), 200
