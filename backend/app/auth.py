"""Stateless JWT authentication.

Tokens are signed with JWT_SECRET and carry the user id and role. Because no
session is stored on the server, any app-tier instance behind the load
balancer can serve any request, which keeps horizontal scaling simple.
"""
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import query
from .errors import ApiError


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def create_token(user):
    cfg = current_app.config["RENTEASE"]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "iat": now,
        "exp": now + timedelta(hours=cfg.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm="HS256")


def _current_user_from_request():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    cfg = current_app.config["RENTEASE"]
    try:
        payload = jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "Your session has expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise ApiError(401, "Invalid authentication token.")
    user = query(
        "SELECT id, name, email, role, phone, is_active, created_at FROM users WHERE id = %s",
        (int(payload["sub"]),),
        one=True,
    )
    if not user or not user["is_active"]:
        raise ApiError(401, "Account not found or disabled.")
    return public_user(user)


def load_optional_user():
    """Set g.user if a valid token is present; never fails for anonymous users."""
    try:
        g.user = _current_user_from_request()
    except ApiError:
        g.user = None
    return g.user


def login_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = _current_user_from_request()
            if user is None:
                raise ApiError(401, "Please log in to continue.")
            if roles and user["role"] not in roles:
                raise ApiError(403, "You do not have permission to do this.")
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def public_user(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "phone": row.get("phone"),
        "is_active": bool(row.get("is_active", True)),
        "created_at": row.get("created_at"),
    }
