"""API tests. Run with:  python -m pytest -q   (from the backend folder)

They use a throwaway SQLite database so they can run in CI without a
database server. The CI pipeline runs these before building the image.
"""
import io
import os
import struct
import sys
import tempfile
import zlib

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402


def tiny_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"\x00\xff\x00\x00"  # one red pixel
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


@pytest.fixture()
def client():
    tmp = tempfile.mkdtemp()
    cfg = Config(
        DATABASE_URL="sqlite:///" + os.path.join(tmp, "test.db"),
        UPLOAD_DIR=os.path.join(tmp, "uploads"),
        STORAGE_BACKEND="local",
        JWT_SECRET="test-secret-" + "x" * 32,
        ADMIN_EMAIL="admin@test.pk",
        ADMIN_PASSWORD="AdminPass123",
        CORS_ORIGINS=["http://localhost:8080"],
        LOG_LEVEL="WARNING",
    )
    app = create_app(cfg)
    return app.test_client()


def register(client, email, role, name="Test User"):
    res = client.post("/api/auth/register", json={
        "name": name, "email": email, "password": "Secret123", "role": role, "phone": "0300-1234567"})
    assert res.status_code == 201, res.get_json()
    return {"Authorization": "Bearer " + res.get_json()["token"]}


def login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.get_json()
    return {"Authorization": "Bearer " + res.get_json()["token"]}


LISTING = {
    "title": "Nice 2 bed flat in F-11",
    "description": "A lovely flat with a balcony, parking and backup power available.",
    "property_type": "flat",
    "city": "Islamabad",
    "area": "F-11/1",
    "rent": 80000,
    "bedrooms": 2,
    "bathrooms": 2,
    "size_sqft": 1000,
    "furnished": True,
}


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["checks"]["database"] == "ok"


def test_register_validation_and_duplicates(client):
    res = client.post("/api/auth/register", json={"name": "A", "email": "bad", "password": "x", "role": "admin"})
    assert res.status_code == 400
    details = res.get_json()["details"]
    assert {"name", "email", "password", "role"} <= set(details)

    register(client, "dup@test.pk", "tenant")
    res = client.post("/api/auth/register", json={
        "name": "Again", "email": "DUP@test.pk", "password": "Secret123", "role": "tenant"})
    assert res.status_code == 409


def test_login_and_me(client):
    register(client, "me@test.pk", "tenant", name="Me Myself")
    assert client.post("/api/auth/login", json={"email": "me@test.pk", "password": "wrong"}).status_code == 401
    headers = login(client, "me@test.pk", "Secret123")
    res = client.get("/api/auth/me", headers=headers)
    assert res.get_json()["user"]["name"] == "Me Myself"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_full_listing_lifecycle(client):
    owner = register(client, "owner@test.pk", "owner", name="Olivia Owner")
    tenant = register(client, "tenant@test.pk", "tenant", name="Tom Tenant")
    admin = login(client, "admin@test.pk", "AdminPass123")

    # Tenants cannot create listings
    assert client.post("/api/properties", json=LISTING, headers=tenant).status_code == 403

    res = client.post("/api/properties", json=LISTING, headers=owner)
    assert res.status_code == 201
    pid = res.get_json()["id"]
    assert res.get_json()["status"] == "pending"

    # Pending listings are hidden from the public
    assert client.get(f"/api/properties/{pid}").status_code == 404
    assert client.get("/api/properties").get_json()["total"] == 0

    # Image upload: rejects non-images, accepts PNG
    bad = client.post(f"/api/properties/{pid}/images", headers=owner,
                      data={"images": (io.BytesIO(b"<svg></svg>"), "x.png")}, content_type="multipart/form-data")
    assert bad.status_code == 400
    ok = client.post(f"/api/properties/{pid}/images", headers=owner,
                     data={"images": (io.BytesIO(tiny_png()), "flat.png")}, content_type="multipart/form-data")
    assert ok.status_code == 201
    image_url = ok.get_json()["images"][0]["url"]
    assert client.get(image_url).status_code == 200

    # Admin rejection requires a reason, then approval
    assert client.patch(f"/api/admin/properties/{pid}", json={"status": "rejected"}, headers=admin).status_code == 400
    assert client.patch(f"/api/admin/properties/{pid}", json={"status": "approved"}, headers=owner).status_code == 403
    assert client.patch(f"/api/admin/properties/{pid}", json={"status": "approved"}, headers=admin).status_code == 200

    # Public search and filters
    listing = client.get("/api/properties?city=islamabad&min_rent=50000&bedrooms=2").get_json()
    assert listing["total"] == 1 and listing["items"][0]["cover_url"] == image_url
    assert client.get("/api/properties?max_rent=50000").get_json()["total"] == 0
    assert client.get("/api/properties?q=balcony").get_json()["total"] == 1
    assert client.get("/api/properties?type=house").get_json()["total"] == 0
    assert client.get("/api/meta/filters").get_json()["cities"] == ["Islamabad"]

    # Phone is only revealed to signed-in users
    assert "phone" not in client.get(f"/api/properties/{pid}").get_json()["owner"]
    assert client.get(f"/api/properties/{pid}", headers=tenant).get_json()["owner"]["phone"] == "0300-1234567"

    # Inquiry flow
    res = client.post(f"/api/properties/{pid}/inquiries", json={"message": "Is it available next month?"}, headers=tenant)
    assert res.status_code == 201
    iid = res.get_json()["id"]
    dup = client.post(f"/api/properties/{pid}/inquiries", json={"message": "Hello again, any update?"}, headers=tenant)
    assert dup.status_code == 409
    assert client.post(f"/api/properties/{pid}/inquiries", json={"message": "Owner asking self"},
                       headers=owner).status_code == 403

    received = client.get("/api/my/inquiries", headers=owner).get_json()["items"]
    assert received[0]["tenant"]["name"] == "Tom Tenant"
    res = client.patch(f"/api/inquiries/{iid}", json={"reply": "Yes, come visit on Sunday."}, headers=owner)
    assert res.get_json()["status"] == "replied"
    sent = client.get("/api/my/inquiries", headers=tenant).get_json()["items"]
    assert sent[0]["reply"] == "Yes, come visit on Sunday."

    # Another owner cannot touch this listing
    other = register(client, "other@test.pk", "owner")
    assert client.put(f"/api/properties/{pid}", json=LISTING, headers=other).status_code == 403
    assert client.delete(f"/api/properties/{pid}", headers=other).status_code == 403

    # Editing sends the listing back to moderation
    edited = dict(LISTING, rent=85000)
    res = client.put(f"/api/properties/{pid}", json=edited, headers=owner)
    assert res.get_json()["status"] == "pending" and res.get_json()["rent"] == 85000

    stats = client.get("/api/admin/stats", headers=admin).get_json()
    assert stats["properties"]["pending"] == 1 and stats["inquiries"]["total"] == 1

    assert client.delete(f"/api/properties/{pid}", headers=owner).status_code == 200
    assert client.get(image_url).status_code == 404


def test_admin_can_disable_user(client):
    register(client, "bad@test.pk", "tenant")
    admin = login(client, "admin@test.pk", "AdminPass123")
    users = client.get("/api/admin/users", headers=admin).get_json()["items"]
    uid = next(u["id"] for u in users if u["email"] == "bad@test.pk")
    assert client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=admin).status_code == 200
    assert client.post("/api/auth/login", json={"email": "bad@test.pk", "password": "Secret123"}).status_code == 403


def test_cors_and_headers(client):
    res = client.get("/api/health/live", headers={"Origin": "http://localhost:8080"})
    assert res.headers["Access-Control-Allow-Origin"] == "http://localhost:8080"
    assert "Access-Control-Allow-Origin" not in client.get("/api/health/live", headers={"Origin": "http://evil.com"}).headers
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert client.options("/api/properties").status_code in (200, 204)


def test_production_config_rejects_weak_secret():
    cfg = Config(APP_ENV="production", JWT_SECRET="short", DATABASE_URL="postgresql://u:p@h/db")
    with pytest.raises(RuntimeError):
        cfg.validate()
