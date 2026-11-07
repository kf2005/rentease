from flask import Blueprint, g, jsonify

from ..auth import login_required
from ..db import commit, execute, query
from ..errors import ApiError
from ..validation import Validator, json_body

bp = Blueprint("inquiries", __name__)

INQUIRY_SELECT = """
    SELECT q.id, q.property_id, q.message, q.contact_phone, q.status, q.reply, q.replied_at, q.created_at,
           p.title AS property_title, p.city AS property_city, p.area AS property_area, p.owner_id,
           t.id AS tenant_id, t.name AS tenant_name, t.email AS tenant_email,
           o.name AS owner_name
    FROM inquiries q
    JOIN properties p ON p.id = q.property_id
    JOIN users t ON t.id = q.tenant_id
    JOIN users o ON o.id = p.owner_id
"""


def serialize_inquiry(row, viewer_role):
    out = {
        "id": row["id"],
        "message": row["message"],
        "status": row["status"],
        "reply": row["reply"],
        "replied_at": row["replied_at"],
        "created_at": row["created_at"],
        "property": {
            "id": row["property_id"],
            "title": row["property_title"],
            "city": row["property_city"],
            "area": row["property_area"],
        },
    }
    if viewer_role in ("owner", "admin"):
        out["tenant"] = {
            "id": row["tenant_id"],
            "name": row["tenant_name"],
            "email": row["tenant_email"],
            "phone": row["contact_phone"],
        }
    else:
        out["owner"] = {"name": row["owner_name"]}
        out["contact_phone"] = row["contact_phone"]
    return out


@bp.post("/properties/<int:property_id>/inquiries")
@login_required("tenant")
def create_inquiry(property_id):
    prop = query("SELECT id, owner_id, status FROM properties WHERE id = %s", (property_id,), one=True)
    if not prop or prop["status"] != "approved":
        raise ApiError(404, "Listing not found.")
    v = Validator(json_body())
    v.string("message", min_len=10, max_len=2000).phone("contact_phone")
    clean = v.result()

    open_inquiry = query(
        "SELECT id FROM inquiries WHERE property_id = %s AND tenant_id = %s AND status = 'new'",
        (property_id, g.user["id"]),
        one=True,
    )
    if open_inquiry:
        raise ApiError(409, "You already have an open inquiry for this listing. Please wait for the owner to reply.")

    row = execute(
        "INSERT INTO inquiries (property_id, tenant_id, message, contact_phone) VALUES (%s, %s, %s, %s) RETURNING id",
        (property_id, g.user["id"], clean["message"], clean.get("contact_phone") or g.user.get("phone")),
        returning=True,
    )
    commit()
    created = query(INQUIRY_SELECT + " WHERE q.id = %s", (row["id"],), one=True)
    return jsonify(serialize_inquiry(created, "tenant")), 201


@bp.get("/my/inquiries")
@login_required("owner", "tenant")
def my_inquiries():
    if g.user["role"] == "owner":
        rows = query(INQUIRY_SELECT + " WHERE p.owner_id = %s ORDER BY q.created_at DESC, q.id DESC", (g.user["id"],))
    else:
        rows = query(INQUIRY_SELECT + " WHERE q.tenant_id = %s ORDER BY q.created_at DESC, q.id DESC", (g.user["id"],))
    return jsonify({"items": [serialize_inquiry(r, g.user["role"]) for r in rows]})


@bp.patch("/inquiries/<int:inquiry_id>")
@login_required("owner", "tenant")
def update_inquiry(inquiry_id):
    row = query(INQUIRY_SELECT + " WHERE q.id = %s", (inquiry_id,), one=True)
    if not row:
        raise ApiError(404, "Inquiry not found.")
    data = json_body()

    if g.user["role"] == "tenant":
        # Tenants may only close their own inquiry.
        if row["tenant_id"] != g.user["id"]:
            raise ApiError(403, "This is not your inquiry.")
        if data.get("status") != "closed":
            raise ApiError(400, "Tenants can only close an inquiry.")
        execute("UPDATE inquiries SET status = 'closed' WHERE id = %s", (inquiry_id,))
    else:
        if row["owner_id"] != g.user["id"]:
            raise ApiError(403, "This inquiry is not for one of your listings.")
        if "reply" in data:
            v = Validator(data)
            v.string("reply", min_len=2, max_len=2000)
            clean = v.result()
            execute(
                "UPDATE inquiries SET reply = %s, status = 'replied', replied_at = CURRENT_TIMESTAMP WHERE id = %s",
                (clean["reply"], inquiry_id),
            )
        elif data.get("status") == "closed":
            execute("UPDATE inquiries SET status = 'closed' WHERE id = %s", (inquiry_id,))
        else:
            raise ApiError(400, "Send a reply, or set status to 'closed'.")
    commit()
    updated = query(INQUIRY_SELECT + " WHERE q.id = %s", (inquiry_id,), one=True)
    return jsonify(serialize_inquiry(updated, g.user["role"]))
