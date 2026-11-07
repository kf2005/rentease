from flask import Blueprint, g, jsonify

from ..auth import create_token, hash_password, login_required, public_user, verify_password
from ..db import commit, execute, is_unique_violation, query
from ..errors import ApiError
from ..validation import Validator, json_body

bp = Blueprint("auth", __name__)


@bp.post("/auth/register")
def register():
    data = json_body()
    v = Validator(data)
    v.string("name", min_len=2, max_len=100).email().phone()
    v.string("password", min_len=8, max_len=128)
    v.choice("role", ("owner", "tenant"))  # admins cannot self-register
    clean = v.result()

    try:
        user = execute(
            """INSERT INTO users (name, email, password_hash, role, phone)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING id, name, email, role, phone, is_active, created_at""",
            (clean["name"], clean["email"], hash_password(clean["password"]), clean["role"], clean.get("phone")),
            returning=True,
        )
        commit()
    except Exception as exc:
        if is_unique_violation(exc):
            raise ApiError(409, "An account with this email already exists.", {"email": "Email already registered."})
        raise
    user = public_user(user)
    return jsonify({"token": create_token(user), "user": user}), 201


@bp.post("/auth/login")
def login():
    data = json_body()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not email or not password:
        raise ApiError(400, "Email and password are required.")
    row = query("SELECT * FROM users WHERE email = %s", (email,), one=True)
    if not row or not verify_password(row["password_hash"], password):
        raise ApiError(401, "Incorrect email or password.")
    if not row["is_active"]:
        raise ApiError(403, "This account has been disabled. Contact support.")
    user = public_user(row)
    return jsonify({"token": create_token(user), "user": user})


@bp.get("/auth/me")
@login_required()
def me():
    return jsonify({"user": g.user})


@bp.put("/auth/me")
@login_required()
def update_me():
    data = json_body()
    v = Validator(data)
    v.string("name", min_len=2, max_len=100).phone()
    clean = v.result()
    user = execute(
        "UPDATE users SET name = %s, phone = %s WHERE id = %s RETURNING id, name, email, role, phone, is_active, created_at",
        (clean["name"], clean.get("phone"), g.user["id"]),
        returning=True,
    )
    commit()
    return jsonify({"user": public_user(user)})
