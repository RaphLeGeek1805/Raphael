"""
ACCESKEY Smart Hosting — Flask application factory
Run: python app.py
"""
import os
import logging
from datetime import datetime, timedelta

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from config import DevelopmentConfig
from models import db, User, Property, Lock, AccessCode, Booking


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)


def create_app(config_object=None):
    app = Flask(__name__)

    # Configuration
    if config_object is None:
        env = os.environ.get("FLASK_ENV", "development")
        from config import config_by_name
        app.config.from_object(config_by_name.get(env, DevelopmentConfig))
    else:
        app.config.from_object(config_object)

    # Extensions
    db.init_app(app)
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints
    from routes.auth import auth_bp
    from routes.properties import properties_bp
    from routes.locks import locks_bp
    from routes.access_codes import codes_bp
    from routes.bookings import bookings_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(properties_bp, url_prefix="/api/properties")
    app.register_blueprint(locks_bp, url_prefix="/api/locks")
    app.register_blueprint(codes_bp, url_prefix="/api/codes")
    app.register_blueprint(bookings_bp, url_prefix="/api/bookings")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    # Health check
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "ACCESKEY Smart Hosting"}), 200

    # JWT error handlers
    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Authentication required"}), 401

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    return app


def seed_demo_data(app):
    """Populate the database with demo data for testing."""
    with app.app_context():
        # Avoid re-seeding
        if User.query.filter_by(email="demo@acceskey.fr").first():
            app.logger.info("Demo data already present — skipping seed.")
            return

        app.logger.info("Seeding demo data…")

        # --- Users ---
        host = User(email="demo@acceskey.fr", name="Marie Dupont", role="host", plan="pro")
        host.set_password("Demo1234!")

        admin = User(email="admin@acceskey.fr", name="Admin ACCESKEY", role="admin", plan="business")
        admin.set_password("Admin1234!")

        db.session.add_all([host, admin])
        db.session.flush()  # get IDs

        # --- Properties ---
        prop1 = Property(
            user_id=host.id,
            name="Studio Montmartre",
            address="12 Rue Lepic",
            city="Paris",
            type="studio",
            platform="airbnb",
            active=True,
        )
        prop2 = Property(
            user_id=host.id,
            name="Appartement Lyon Centre",
            address="45 Rue de la République",
            city="Lyon",
            type="apartment",
            platform="both",
            active=True,
        )
        db.session.add_all([prop1, prop2])
        db.session.flush()

        # --- Locks ---
        now = datetime.utcnow()
        lock1 = Lock(
            property_id=prop1.id,
            name="Porte d'entrée",
            model="Nuki Smart Lock 4.0",
            serial_number="NK-2024-00123",
            status="online",
            battery_level=87,
            last_seen_at=now,
            provider="nuki",
            external_lock_id="nuki_123456",
        )
        lock2 = Lock(
            property_id=prop1.id,
            name="Boîte à clés",
            model="igloohome Keybox 3",
            serial_number="IGL-2024-00456",
            status="online",
            battery_level=45,
            last_seen_at=now,
            provider="igloohome",
            external_lock_id="igl_654321",
        )
        lock3 = Lock(
            property_id=prop2.id,
            name="Entrée principale",
            model="Yale Linus Smart Lock",
            serial_number="YALE-2024-00789",
            status="low_battery",
            battery_level=12,
            last_seen_at=now - timedelta(hours=2),
            provider="yale",
            external_lock_id="yale_789012",
        )
        db.session.add_all([lock1, lock2, lock3])
        db.session.flush()

        # --- Bookings ---
        booking1 = Booking(
            property_id=prop1.id,
            platform="airbnb",
            guest_name="Alice Martin",
            guest_email="alice.martin@email.com",
            guest_phone="+33612345678",
            check_in=now + timedelta(days=2),
            check_out=now + timedelta(days=5),
            status="upcoming",
            external_booking_id="ABB-2024-001",
        )
        booking2 = Booking(
            property_id=prop1.id,
            platform="booking",
            guest_name="Bob Leclerc",
            guest_email="bob.leclerc@email.com",
            guest_phone="+33698765432",
            check_in=now - timedelta(days=1),
            check_out=now + timedelta(days=2),
            status="active",
            access_code_sent=True,
            external_booking_id="BK-2024-042",
        )
        booking3 = Booking(
            property_id=prop2.id,
            platform="direct",
            guest_name="Chloé Bernard",
            guest_email="chloe.b@email.com",
            guest_phone="+33756789012",
            check_in=now + timedelta(days=7),
            check_out=now + timedelta(days=10),
            status="upcoming",
        )
        db.session.add_all([booking1, booking2, booking3])
        db.session.flush()

        # --- Access Codes ---
        from services.code_generator import generate_unique_code_for_lock, hash_code

        # Code for active booking on lock1
        code_val = generate_unique_code_for_lock(
            lock1.id, booking2.check_in, booking2.check_out
        )
        code1 = AccessCode(
            lock_id=lock1.id,
            booking_id=booking2.id,
            code_hash=hash_code(code_val),
            code_display=code_val,
            guest_name=booking2.guest_name,
            guest_email=booking2.guest_email,
            guest_phone=booking2.guest_phone,
            valid_from=booking2.check_in,
            valid_until=booking2.check_out,
            status="active",
        )
        db.session.add(code1)

        # An old expired code
        old_from = now - timedelta(days=10)
        old_until = now - timedelta(days=7)
        old_code_val = generate_unique_code_for_lock(lock1.id, old_from, old_until)
        code2 = AccessCode(
            lock_id=lock1.id,
            code_hash=hash_code(old_code_val),
            code_display=old_code_val,
            guest_name="Previous Guest",
            guest_email="prev@email.com",
            valid_from=old_from,
            valid_until=old_until,
            status="expired",
        )
        db.session.add(code2)

        db.session.commit()
        app.logger.info(
            "Demo data seeded.\n"
            "  Host login   : demo@acceskey.fr / Demo1234!\n"
            "  Admin login  : admin@acceskey.fr / Admin1234!"
        )


if __name__ == "__main__":
    app = create_app()

    with app.app_context():
        db.create_all()
        seed_demo_data(app)

    app.run(debug=True, host="0.0.0.0", port=5000)
