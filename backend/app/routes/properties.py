from flask import Blueprint, abort, current_app, g, jsonify, request, send_from_directory

from ..auth import load_optional_user, login_required
from ..db import commit, execute, query
from ..errors import ApiError
from ..storage import ALLOWED_IMAGE_TYPES, detect_image_type, new_key
from ..validation import PROPERTY_TYPES, Validator, json_body, query_int

bp = Blueprint("properties", __name__)

SORTS = {
    "newest": "p.created_at DESC, p.id DESC",
    "rent_asc": "p.rent ASC, p.id DESC",
    "rent_desc": "p.rent DESC, p.id DESC",
}

COVER_SUBQUERY = (
    "(SELECT i.storage_key FROM property_images i WHERE i.property_id = p.id "
    "ORDER BY i.sort_order, i.id LIMIT 1) AS cover_key"
)


def storage():
    return current_app.extensions["rentease_storage"]


def serialize_property(row, images=None, include_private=False):
    out = {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "property_type": row["property_type"],
        "city": row["city"],
        "area": row["area"],
        "address": row.get("address"),
        "rent": row["rent"],
        "bedrooms": row["bedrooms"],
        "bathrooms": row["bathrooms"],
        "size_sqft": row.get("size_sqft"),
        "furnished": bool(row["furnished"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
        "owner": {"id": row["owner_id"], "name": row.get("owner_name")},
    }
    if "cover_key" in row:
        out["cover_url"] = storage().url(row["cover_key"]) if row["cover_key"] else None
    if images is not None:
        out["images"] = [{"id": i["id"], "url": storage().url(i["storage_key"])} for i in images]
        out["cover_url"] = out["images"][0]["url"] if out["images"] else None
    if include_private:
        out["rejection_reason"] = row.get("rejection_reason")
        out["owner"]["phone"] = row.get("owner_phone")
        out["owner"]["email"] = row.get("owner_email")
    if "inquiry_count" in row:
        out["inquiry_count"] = row["inquiry_count"]
    return out


def property_validator(data):
    v = Validator(data)
    v.string("title", min_len=5, max_len=150)
    v.string("description", min_len=20, max_len=5000)
    v.choice("property_type", PROPERTY_TYPES, label="Property type")
    v.string("city", min_len=2, max_len=60)
    v.string("area", min_len=2, max_len=100)
    v.string("address", required=False, max_len=255)
    v.integer("rent", min_value=1000, max_value=10_000_000)
    v.integer("bedrooms", min_value=0, max_value=20)
    v.integer("bathrooms", min_value=0, max_value=20)
    v.integer("size_sqft", required=False, min_value=50, max_value=100_000, label="Size (sq ft)")
    v.boolean("furnished")
    return v.result()


def get_property_or_404(property_id):
    row = query(
        """SELECT p.*, u.name AS owner_name, u.phone AS owner_phone, u.email AS owner_email
           FROM properties p JOIN users u ON u.id = p.owner_id WHERE p.id = %s""",
        (property_id,),
        one=True,
    )
    if not row:
        raise ApiError(404, "Listing not found.")
    return row


def require_owner(row):
    if g.user["role"] != "admin" and row["owner_id"] != g.user["id"]:
        raise ApiError(403, "You can only manage your own listings.")


def property_images(property_id):
    return query(
        "SELECT id, storage_key FROM property_images WHERE property_id = %s ORDER BY sort_order, id",
        (property_id,),
    )


# -- public browsing ---------------------------------------------------------
@bp.get("/properties")
def list_properties():
    where = ["p.status = %s"]
    params = ["approved"]

    city = request.args.get("city", "").strip()
    if city:
        where.append("LOWER(p.city) = LOWER(%s)")
        params.append(city)
    area = request.args.get("area", "").strip()
    if area:
        where.append("LOWER(p.area) LIKE %s")
        params.append(f"%{area.lower()}%")
    q = request.args.get("q", "").strip()
    if q:
        where.append("(LOWER(p.title) LIKE %s OR LOWER(p.description) LIKE %s OR LOWER(p.area) LIKE %s)")
        params.extend([f"%{q.lower()}%"] * 3)
    ptype = request.args.get("type", "").strip()
    if ptype:
        if ptype not in PROPERTY_TYPES:
            raise ApiError(400, "Unknown property type.")
        where.append("p.property_type = %s")
        params.append(ptype)
    min_rent = query_int("min_rent", min_value=0)
    if min_rent is not None:
        where.append("p.rent >= %s")
        params.append(min_rent)
    max_rent = query_int("max_rent", min_value=0)
    if max_rent is not None:
        where.append("p.rent <= %s")
        params.append(max_rent)
    bedrooms = query_int("bedrooms", min_value=0)
    if bedrooms is not None:
        where.append("p.bedrooms >= %s")
        params.append(bedrooms)
    if request.args.get("furnished") in ("true", "1"):
        where.append("p.furnished = %s")
        params.append(True)

    sort = SORTS.get(request.args.get("sort", "newest"), SORTS["newest"])
    page = query_int("page", 1, min_value=1)
    page_size = query_int("page_size", 9, min_value=1, max_value=50)
    where_sql = " AND ".join(where)

    total = query(f"SELECT COUNT(*) AS n FROM properties p WHERE {where_sql}", params, one=True)["n"]
    rows = query(
        f"""SELECT p.*, u.name AS owner_name, {COVER_SUBQUERY}
            FROM properties p JOIN users u ON u.id = p.owner_id
            WHERE {where_sql} ORDER BY {sort} LIMIT %s OFFSET %s""",
        params + [page_size, (page - 1) * page_size],
    )
    return jsonify(
        {
            "items": [serialize_property(r) for r in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max(1, -(-total // page_size)),
        }
    )


@bp.get("/meta/filters")
def filter_options():
    cities = query(
        "SELECT city, COUNT(*) AS n FROM properties WHERE status = %s GROUP BY city ORDER BY city",
        ("approved",),
    )
    return jsonify({"cities": [c["city"] for c in cities], "property_types": list(PROPERTY_TYPES)})


@bp.get("/properties/<int:property_id>")
def get_property(property_id):
    user = load_optional_user()
    row = get_property_or_404(property_id)
    is_manager = bool(user and (user["role"] == "admin" or user["id"] == row["owner_id"]))
    if row["status"] != "approved" and not is_manager:
        raise ApiError(404, "Listing not found.")
    data = serialize_property(row, images=property_images(property_id), include_private=is_manager)
    if user:  # contact details only for signed-in users (limits scraping)
        data["owner"]["phone"] = row.get("owner_phone")
    data["can_manage"] = is_manager
    return jsonify(data)


# -- owner management ----------------------------------------------------------
@bp.get("/my/properties")
@login_required("owner")
def my_properties():
    rows = query(
        f"""SELECT p.*, u.name AS owner_name, {COVER_SUBQUERY},
                   (SELECT COUNT(*) FROM inquiries q WHERE q.property_id = p.id) AS inquiry_count
            FROM properties p JOIN users u ON u.id = p.owner_id
            WHERE p.owner_id = %s ORDER BY p.created_at DESC, p.id DESC""",
        (g.user["id"],),
    )
    return jsonify({"items": [serialize_property(r, include_private=True) for r in rows]})


@bp.post("/properties")
@login_required("owner")
def create_property():
    c = property_validator(json_body())
    row = execute(
        """INSERT INTO properties (owner_id, title, description, property_type, city, area, address,
                                   rent, bedrooms, bathrooms, size_sqft, furnished, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending') RETURNING id""",
        (g.user["id"], c["title"], c["description"], c["property_type"], c["city"], c["area"], c.get("address"),
         c["rent"], c["bedrooms"], c["bathrooms"], c.get("size_sqft"), c["furnished"]),
        returning=True,
    )
    commit()
    created = get_property_or_404(row["id"])
    return jsonify(serialize_property(created, images=[], include_private=True)), 201


@bp.put("/properties/<int:property_id>")
@login_required("owner", "admin")
def update_property(property_id):
    row = get_property_or_404(property_id)
    require_owner(row)
    c = property_validator(json_body())
    # Edits by an owner go back to the moderation queue.
    new_status = row["status"] if g.user["role"] == "admin" else "pending"
    execute(
        """UPDATE properties SET title = %s, description = %s, property_type = %s, city = %s, area = %s,
                  address = %s, rent = %s, bedrooms = %s, bathrooms = %s, size_sqft = %s, furnished = %s,
                  status = %s, rejection_reason = NULL, updated_at = CURRENT_TIMESTAMP
           WHERE id = %s""",
        (c["title"], c["description"], c["property_type"], c["city"], c["area"], c.get("address"), c["rent"],
         c["bedrooms"], c["bathrooms"], c.get("size_sqft"), c["furnished"], new_status, property_id),
    )
    commit()
    updated = get_property_or_404(property_id)
    return jsonify(serialize_property(updated, images=property_images(property_id), include_private=True))


@bp.delete("/properties/<int:property_id>")
@login_required("owner", "admin")
def delete_property(property_id):
    row = get_property_or_404(property_id)
    require_owner(row)
    keys = [i["storage_key"] for i in property_images(property_id)]
    execute("DELETE FROM properties WHERE id = %s", (property_id,))
    commit()
    for key in keys:
        try:
            storage().delete(key)
        except Exception:
            current_app.logger.warning("Could not delete image %s", key)
    return jsonify({"deleted": True})


# -- images ------------------------------------------------------------------
@bp.post("/properties/<int:property_id>/images")
@login_required("owner")
def upload_images(property_id):
    row = get_property_or_404(property_id)
    require_owner(row)
    cfg = current_app.config["RENTEASE"]
    files = request.files.getlist("images")
    if not files:
        raise ApiError(400, "Choose at least one image to upload.")
    existing = len(property_images(property_id))
    if existing + len(files) > cfg.MAX_IMAGES_PER_PROPERTY:
        raise ApiError(400, f"A listing can have at most {cfg.MAX_IMAGES_PER_PROPERTY} images.")

    prepared = []
    for f in files:
        data = f.read()
        if len(data) > cfg.MAX_IMAGE_MB * 1024 * 1024:
            raise ApiError(400, f"'{f.filename}' is larger than {cfg.MAX_IMAGE_MB} MB.")
        ext = detect_image_type(data)
        if not ext:
            raise ApiError(400, f"'{f.filename}' is not a JPG, PNG or WebP image.")
        prepared.append((data, ext))

    for offset, (data, ext) in enumerate(prepared):
        key = new_key(property_id, ext)
        storage().save(key, data, ALLOWED_IMAGE_TYPES[ext])
        execute(
            "INSERT INTO property_images (property_id, storage_key, sort_order) VALUES (%s, %s, %s)",
            (property_id, key, existing + offset),
        )
    commit()
    images = property_images(property_id)
    return jsonify({"images": [{"id": i["id"], "url": storage().url(i["storage_key"])} for i in images]}), 201


@bp.delete("/images/<int:image_id>")
@login_required("owner", "admin")
def delete_image(image_id):
    img = query(
        """SELECT i.id, i.storage_key, p.owner_id FROM property_images i
           JOIN properties p ON p.id = i.property_id WHERE i.id = %s""",
        (image_id,),
        one=True,
    )
    if not img:
        raise ApiError(404, "Image not found.")
    require_owner(img)
    execute("DELETE FROM property_images WHERE id = %s", (image_id,))
    commit()
    try:
        storage().delete(img["storage_key"])
    except Exception:
        current_app.logger.warning("Could not delete image %s", img["storage_key"])
    return jsonify({"deleted": True})


@bp.get("/uploads/<path:key>")
def serve_upload(key):
    """Only used with STORAGE_BACKEND=local; S3 images are served by S3/CloudFront."""
    cfg = current_app.config["RENTEASE"]
    if cfg.STORAGE_BACKEND != "local":
        abort(404)
    response = send_from_directory(cfg.UPLOAD_DIR, key, max_age=86400)
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    return response
