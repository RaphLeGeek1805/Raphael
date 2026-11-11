import secrets
import hashlib
from datetime import datetime
from flask import current_app


def generate_pin(length=6):
    """Generate a cryptographically secure PIN of given length."""
    # Use secrets module for cryptographic security
    digits = "0123456789"
    pin = "".join(secrets.choice(digits) for _ in range(length))
    return pin


def hash_code(code):
    """Hash a PIN code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def is_code_unique_for_lock(lock_id, code, valid_from, valid_until, exclude_id=None):
    """
    Check if a code is unique for a given lock during the specified period.
    Two codes on the same lock must not overlap.
    """
    from models import AccessCode

    code_hash = hash_code(code)
    query = AccessCode.query.filter(
        AccessCode.lock_id == lock_id,
        AccessCode.code_hash == code_hash,
        AccessCode.status == "active",
        AccessCode.valid_from < valid_until,
        AccessCode.valid_until > valid_from,
    )
    if exclude_id:
        query = query.filter(AccessCode.id != exclude_id)
    return query.count() == 0


def generate_unique_code_for_lock(lock_id, valid_from, valid_until, length=6, max_attempts=50):
    """
    Generate a unique PIN code for a lock during the given validity period.
    Raises ValueError if unable to find a unique code after max_attempts.
    """
    for attempt in range(max_attempts):
        code = generate_pin(length)
        if is_code_unique_for_lock(lock_id, code, valid_from, valid_until):
            current_app.logger.info(
                f"Generated unique code for lock {lock_id} after {attempt + 1} attempt(s)"
            )
            return code
    raise ValueError(
        f"Unable to generate a unique code for lock {lock_id} after {max_attempts} attempts"
    )
