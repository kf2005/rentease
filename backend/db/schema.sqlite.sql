-- RentEase schema for SQLite (local development and automated tests only).
-- Mirrors schema.postgres.sql.

CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT     NOT NULL,
    email          TEXT     NOT NULL UNIQUE,
    password_hash  TEXT     NOT NULL,
    role           TEXT     NOT NULL CHECK (role IN ('owner', 'tenant', 'admin')),
    phone          TEXT,
    is_active      INTEGER  NOT NULL DEFAULT 1,
    created_at     TEXT     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS properties (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id          INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             TEXT     NOT NULL,
    description       TEXT     NOT NULL,
    property_type     TEXT     NOT NULL CHECK (property_type IN ('house', 'flat', 'portion', 'room', 'studio')),
    city              TEXT     NOT NULL,
    area              TEXT     NOT NULL,
    address           TEXT,
    rent              INTEGER  NOT NULL CHECK (rent > 0),
    bedrooms          INTEGER  NOT NULL CHECK (bedrooms >= 0),
    bathrooms         INTEGER  NOT NULL CHECK (bathrooms >= 0),
    size_sqft         INTEGER  CHECK (size_sqft IS NULL OR size_sqft > 0),
    furnished         INTEGER  NOT NULL DEFAULT 0,
    status            TEXT     NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason  TEXT,
    created_at        TEXT     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_properties_status_city_rent ON properties (status, city, rent);
CREATE INDEX IF NOT EXISTS idx_properties_owner ON properties (owner_id);

CREATE TABLE IF NOT EXISTS property_images (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id  INTEGER  NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    storage_key  TEXT     NOT NULL,
    sort_order   INTEGER  NOT NULL DEFAULT 0,
    created_at   TEXT     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_property_images_property ON property_images (property_id);

CREATE TABLE IF NOT EXISTS inquiries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id    INTEGER  NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    tenant_id      INTEGER  NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message        TEXT     NOT NULL,
    contact_phone  TEXT,
    status         TEXT     NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'replied', 'closed')),
    reply          TEXT,
    replied_at     TEXT,
    created_at     TEXT     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inquiries_property ON inquiries (property_id);
CREATE INDEX IF NOT EXISTS idx_inquiries_tenant ON inquiries (tenant_id);
