"""Password hashing and session helpers — kept out of templates."""

from __future__ import annotations

import re

from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password_hash: str, password: str) -> bool:
    if not password_hash:
        return False
    return check_password_hash(password_hash, password)


def validate_registration(name: str, email: str, password: str, confirm: str) -> list[str]:
    errors = []
    if not name or len(name.strip()) < 2:
        errors.append("Enter your full name.")
    if not email or not EMAIL_RE.match(email.strip()):
        errors.append("Enter a valid email address.")
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if password != confirm:
        errors.append("Password and confirmation do not match.")
    return errors
