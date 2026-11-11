from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, Property, Lock, AccessCode, Booking

dashboard_bp = Blueprint("dashboard", __name__)


def _get_current_user():
    return User.query.get(int(get_jwt_identity()))


@dashboard_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    """Return KPIs for the dashboard."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    nb_properties = len(prop_ids)
    nb_locks = len(lock_ids)
    nb_online = Lock.query.filter(Lock.id.in_(lock_ids), Lock.status == "online").count()
    nb_low_battery = Lock.query.filter(
        Lock.id.in_(lock_ids), Lock.battery_level < 20
    ).count()
    nb_offline = Lock.query.filter(Lock.id.in_(lock_ids), Lock.status == "offline").count()

    # Accesses today: codes that were used today (used_at) or active codes valid today
    accesses_today = AccessCode.query.filter(
        AccessCode.lock_id.in_(lock_ids),
        AccessCode.valid_from <= today_end,
        AccessCode.valid_until >= today_start,
        AccessCode.status == "active",
    ).count()

    # Active bookings
    active_bookings = Booking.query.filter(
        Booking.property_id.in_(prop_ids),
        Booking.status == "active",
    ).count()

    # Upcoming this week
    next_week = now + timedelta(days=7)
    upcoming_bookings = Booking.query.filter(
        Booking.property_id.in_(prop_ids),
        Booking.status == "upcoming",
        Booking.check_in <= next_week,
    ).count()

    # Alerts
    alerts = []
    if nb_offline > 0:
        alerts.append({"type": "offline", "message": f"{nb_offline} lock(s) offline", "severity": "error"})
    if nb_low_battery > 0:
        alerts.append({"type": "battery", "message": f"{nb_low_battery} lock(s) with low battery (<20%)", "severity": "warning"})

    return jsonify({
        "properties": nb_properties,
        "locks": nb_locks,
        "locks_online": nb_online,
        "locks_offline": nb_offline,
        "locks_low_battery": nb_low_battery,
        "accesses_today": accesses_today,
        "active_bookings": active_bookings,
        "upcoming_bookings_7d": upcoming_bookings,
        "alerts": alerts,
        "plan": user.plan,
    }), 200


@dashboard_bp.route("/recent-access", methods=["GET"])
@jwt_required()
def recent_access():
    """Return 10 most recent access codes (by creation)."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]
    lock_ids = [l.id for l in Lock.query.filter(Lock.property_id.in_(prop_ids)).all()]

    codes = (
        AccessCode.query.filter(AccessCode.lock_id.in_(lock_ids))
        .order_by(AccessCode.created_at.desc())
        .limit(10)
        .all()
    )

    # Enrich with lock/property name
    result = []
    for code in codes:
        item = code.to_dict()
        lock = Lock.query.get(code.lock_id)
        if lock:
            item["lock_name"] = lock.name
            prop = Property.query.get(lock.property_id)
            if prop:
                item["property_name"] = prop.name
        result.append(item)

    return jsonify({"recent_access": result}), 200


@dashboard_bp.route("/upcoming", methods=["GET"])
@jwt_required()
def upcoming():
    """Return upcoming bookings in the next 7 days."""
    user = _get_current_user()
    prop_ids = [p.id for p in Property.query.filter_by(user_id=user.id).all()]

    now = datetime.utcnow()
    next_week = now + timedelta(days=7)

    bookings = (
        Booking.query.filter(
            Booking.property_id.in_(prop_ids),
            Booking.status.in_(["upcoming", "active"]),
            Booking.check_in <= next_week,
        )
        .order_by(Booking.check_in.asc())
        .all()
    )

    result = []
    for b in bookings:
        item = b.to_dict()
        prop = Property.query.get(b.property_id)
        if prop:
            item["property_name"] = prop.name
        result.append(item)

    return jsonify({"upcoming": result}), 200
