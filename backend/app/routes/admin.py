from flask import Blueprint, g, jsonify, request

from ..auth import login_required, public_user
from ..db import commit, execute, query
from ..errors import ApiError
from ..validation import json_body
from .properties import COVER_SUBQUERY, get_property_or_404, serialize_property

bp = Blueprint("admin", __name__)


@bp.get("/admin/stats")
@login_required("admin")
def stats():
    def count(sql, params=()):
        return query(sql, params, one=True)["n"]

    return jsonify(
        {
            "properties": {
                "total": count("SELECT COUNT(*) AS n FROM properties"),
                "pending": count("SELECT COUNT(*) AS n FROM properties WHERE status = %s", ("pending",)),
                "approved": count("SELECT COUNT(*) AS n FROM properties WHERE status = %s", ("approved",)),
                "rejected": count("SELECT COUNT(*) AS n FROM properties WHERE status = %s", ("rejected",)),
            },
            "users": {
                "total": count("SELECT COUNT(*) AS n FROM users"),
                "owners": count("SELECT COUNT(*) AS n FROM users WHERE role = %s", ("owner",)),
                "tenants": count("SELECT COUNT(*) AS n FROM users WHERE role = %s", ("tenant",)),
            },
            "inquiries": {
                "total": count("SELECT COUNT(*) AS n FROM inquiries"),
                "open": count("SELECT COUNT(*) AS n FROM inquiries WHERE status = %s", ("new",)),
            },
        }
    )


@bp.get("/admin/properties")
@login_required("admin")
def admin_properties():
    status = request.args.get("status", "pending")
    params = []
    where = ""
    if status != "all":
        if status not in ("pending", "approved", "rejected"):
            raise ApiError(400, "Unknown status filter.")
        where = "WHERE p.status = %s"
        params.append(status)
    rows = query(
        f"""SELECT p.*, u.name AS owner_name, u.email AS owner_email, u.phone AS owner_phone, {COVER_SUBQUERY}
            FROM properties p JOIN users u ON u.id = p.owner_id {where}
            ORDER BY p.updated_at DESC, p.id DESC""",
        params,
    )
    return jsonify({"items": [serialize_property(r, include_private=True) for r in rows]})


@bp.patch("/admin/properties/<int:property_id>")
@login_required("admin")
def moderate_property(property_id):
    get_property_or_404(property_id)
    data = json_body()
    status = data.get("status")
    if status not in ("approved", "rejected"):
        raise ApiError(400, "Status must be 'approved' or 'rejected'.")
    reason = (data.get("reason") or "").strip()[:255] or None
    if status == "rejected" and not reason:
        raise ApiError(400, "Please give a reason so the owner can fix the listing.", {"reason": "Reason is required."})
    execute(
        "UPDATE properties SET status = %s, rejection_reason = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (status, reason if status == "rejected" else None, property_id),
    )
    commit()
    return jsonify(serialize_property(get_property_or_404(property_id), include_private=True))


@bp.get("/admin/users")
@login_required("admin")
def admin_users():
    rows = query(
        """SELECT u.id, u.name, u.email, u.role, u.phone, u.is_active, u.created_at,
                  (SELECT COUNT(*) FROM properties p WHERE p.owner_id = u.id) AS listing_count
           FROM users u ORDER BY u.created_at DESC, u.id DESC"""
    )
    users = []
    for r in rows:
        u = public_user(r)
        u["listing_count"] = r["listing_count"]
        users.append(u)
    return jsonify({"items": users})


@bp.patch("/admin/users/<int:user_id>")
@login_required("admin")
def set_user_active(user_id):
    if user_id == g.user["id"]:
        raise ApiError(400, "You cannot disable your own account.")
    data = json_body()
    if not isinstance(data.get("is_active"), bool):
        raise ApiError(400, "is_active must be true or false.")
    updated = execute(
        "UPDATE users SET is_active = %s WHERE id = %s RETURNING id, name, email, role, phone, is_active, created_at",
        (data["is_active"], user_id),
        returning=True,
    )
    if not updated:
        raise ApiError(404, "User not found.")
    commit()
    return jsonify({"user": public_user(updated)})
