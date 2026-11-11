from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default="host")  # host/admin/reseller
    plan = db.Column(db.String(50), nullable=False, default="starter")  # starter/pro/business
    plan_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Relationships
    properties = db.relationship("Property", backref="owner", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "plan": self.plan,
            "plan_expires_at": self.plan_expires_at.isoformat() if self.plan_expires_at else None,
            "created_at": self.created_at.isoformat(),
        }


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False, default="apartment")  # apartment/house/studio
    platform = db.Column(db.String(50), nullable=False, default="airbnb")  # airbnb/booking/both
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Relationships
    locks = db.relationship("Lock", backref="property", lazy="dynamic", cascade="all, delete-orphan")
    bookings = db.relationship("Booking", backref="property", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_locks=False):
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "type": self.type,
            "platform": self.platform,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
            "locks_count": self.locks.count(),
        }
        if include_locks:
            data["locks"] = [lock.to_dict() for lock in self.locks]
        return data


class Lock(db.Model):
    __tablename__ = "locks"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    model = db.Column(db.String(100), nullable=True)
    serial_number = db.Column(db.String(100), nullable=True, unique=True)
    status = db.Column(db.String(50), nullable=False, default="online")  # online/offline/low_battery
    battery_level = db.Column(db.Integer, nullable=True, default=100)  # 0-100
    last_seen_at = db.Column(db.DateTime, nullable=True)
    provider = db.Column(db.String(50), nullable=False, default="nuki")  # nuki/yale/igloohome/other
    external_lock_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Relationships
    access_codes = db.relationship("AccessCode", backref="lock", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "property_id": self.property_id,
            "name": self.name,
            "model": self.model,
            "serial_number": self.serial_number,
            "status": self.status,
            "battery_level": self.battery_level,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "provider": self.provider,
            "external_lock_id": self.external_lock_id,
            "created_at": self.created_at.isoformat(),
            "active_codes_count": self.access_codes.filter_by(status="active").count(),
        }


class AccessCode(db.Model):
    __tablename__ = "access_codes"

    id = db.Column(db.Integer, primary_key=True)
    lock_id = db.Column(db.Integer, db.ForeignKey("locks.id"), nullable=False, index=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("bookings.id"), nullable=True, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    code_display = db.Column(db.String(10), nullable=False)  # 4-8 digits
    guest_name = db.Column(db.String(255), nullable=False)
    guest_email = db.Column(db.String(255), nullable=True)
    guest_phone = db.Column(db.String(50), nullable=True)
    valid_from = db.Column(db.DateTime, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="active")  # active/expired/revoked
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    used_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self, show_code=False):
        data = {
            "id": self.id,
            "lock_id": self.lock_id,
            "booking_id": self.booking_id,
            "guest_name": self.guest_name,
            "guest_email": self.guest_email,
            "guest_phone": self.guest_phone,
            "valid_from": self.valid_from.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "used_at": self.used_at.isoformat() if self.used_at else None,
        }
        if show_code:
            data["code"] = self.code_display
        return data


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("properties.id"), nullable=False, index=True)
    platform = db.Column(db.String(50), nullable=False, default="airbnb")  # airbnb/booking/direct
    guest_name = db.Column(db.String(255), nullable=False)
    guest_email = db.Column(db.String(255), nullable=True)
    guest_phone = db.Column(db.String(50), nullable=True)
    check_in = db.Column(db.DateTime, nullable=False)
    check_out = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="upcoming")  # upcoming/active/completed/cancelled
    access_code_sent = db.Column(db.Boolean, nullable=False, default=False)
    external_booking_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Relationships
    access_codes = db.relationship("AccessCode", backref="booking", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "property_id": self.property_id,
            "platform": self.platform,
            "guest_name": self.guest_name,
            "guest_email": self.guest_email,
            "guest_phone": self.guest_phone,
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "status": self.status,
            "access_code_sent": self.access_code_sent,
            "external_booking_id": self.external_booking_id,
            "created_at": self.created_at.isoformat(),
            "access_codes_count": self.access_codes.count(),
        }
