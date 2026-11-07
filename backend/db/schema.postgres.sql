-- RentEase schema for PostgreSQL (Amazon RDS / Azure Database / Cloud SQL).
-- Idempotent: safe to run on every application start.

CREATE TABLE IF NOT EXISTS users (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(100)  NOT NULL,
    email          VARCHAR(255)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255)  NOT NULL,
    role           VARCHAR(10)   NOT NULL CHECK (role IN ('owner', 'tenant', 'admin')),
    phone          VARCHAR(30),
    is_active      BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS properties (
    id                SERIAL PRIMARY KEY,
    owner_id          INTEGER       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title             VARCHAR(150)  NOT NULL,
    description       TEXT          NOT NULL,
    property_type     VARCHAR(20)   NOT NULL CHECK (property_type IN ('house', 'flat', 'portion', 'room', 'studio')),
    city              VARCHAR(60)   NOT NULL,
    area              VARCHAR(100)  NOT NULL,
    address           VARCHAR(255),
    rent              INTEGER       NOT NULL CHECK (rent > 0),
    bedrooms          SMALLINT      NOT NULL CHECK (bedrooms >= 0),
    bathrooms         SMALLINT      NOT NULL CHECK (bathrooms >= 0),
    size_sqft         INTEGER       CHECK (size_sqft IS NULL OR size_sqft > 0),
    furnished         BOOLEAN       NOT NULL DEFAULT FALSE,
    status            VARCHAR(10)   NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    rejection_reason  VARCHAR(255),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_properties_status_city_rent ON properties (status, city, rent);
CREATE INDEX IF NOT EXISTS idx_properties_owner ON properties (owner_id);

CREATE TABLE IF NOT EXISTS property_images (
    id           SERIAL PRIMARY KEY,
    property_id  INTEGER       NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    storage_key  VARCHAR(500)  NOT NULL,
    sort_order   INTEGER       NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_property_images_property ON property_images (property_id);

CREATE TABLE IF NOT EXISTS inquiries (
    id             SERIAL PRIMARY KEY,
    property_id    INTEGER      NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    tenant_id      INTEGER      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message        TEXT         NOT NULL,
    contact_phone  VARCHAR(30),
    status         VARCHAR(10)  NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'replied', 'closed')),
    reply          TEXT,
    replied_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inquiries_property ON inquiries (property_id);
CREATE INDEX IF NOT EXISTS idx_inquiries_tenant ON inquiries (tenant_id);
