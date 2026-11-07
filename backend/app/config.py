"""Application configuration.

Every setting comes from environment variables so the same container image can
run locally, in CI and in the cloud without code changes. Secrets (database
password, JWT secret, admin password) can also be supplied as files via the
``<NAME>_FILE`` convention, which works with Docker secrets, Kubernetes
secrets mounted as files, or values pulled from AWS Secrets Manager / SSM.
Nothing secret is hard-coded for production.
"""
import os
from urllib.parse import quote_plus

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


def load_dotenv(path=".env"):
    """Minimal .env loader for local development (real env vars always win)."""
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()


def env(name, default=None):
    """Read NAME, or the contents of the file at NAME_FILE if that is set."""
    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        with open(file_path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    return os.getenv(name, default)


def env_bool(name, default=False):
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    value = env(name)
    return int(value) if value not in (None, "") else default


def build_database_url():
    """DATABASE_URL wins; otherwise build one from DB_* parts (RDS-friendly)."""
    url = env("DATABASE_URL")
    if url:
        return url
    host = env("DB_HOST")
    if host:
        user = quote_plus(env("DB_USER", "rentease"))
        password = quote_plus(env("DB_PASSWORD", ""))
        port = env("DB_PORT", "5432")
        name = env("DB_NAME", "rentease")
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    # Local development fallback only.
    return "sqlite:///" + os.path.abspath(env("SQLITE_PATH", "rentease-dev.db"))


class Config:
    def __init__(self, **overrides):
        self.APP_ENV = env("APP_ENV", "development")
        self.JWT_SECRET = env("JWT_SECRET", DEV_JWT_SECRET)
        self.JWT_EXPIRES_HOURS = env_int("JWT_EXPIRES_HOURS", 24)

        self.DATABASE_URL = build_database_url()
        # "require" (or "verify-full") encrypts app-tier -> database traffic.
        self.DB_SSLMODE = env("DB_SSLMODE")
        self.DB_POOL_MAX = env_int("DB_POOL_MAX", 10)
        self.AUTO_MIGRATE = env_bool("AUTO_MIGRATE", True)

        origins = env("CORS_ORIGINS", "")
        self.CORS_ORIGINS = [o.strip() for o in origins.split(",") if o.strip()]

        self.STORAGE_BACKEND = env("STORAGE_BACKEND", "local")  # local | s3
        self.UPLOAD_DIR = os.path.abspath(env("UPLOAD_DIR", "uploads"))
        self.S3_BUCKET = env("S3_BUCKET")
        self.S3_PREFIX = env("S3_PREFIX", "uploads/")
        self.AWS_REGION = env("AWS_REGION")
        self.S3_PUBLIC_BASE_URL = env("S3_PUBLIC_BASE_URL")  # e.g. CloudFront URL
        self.S3_URL_EXPIRES = env_int("S3_URL_EXPIRES", 3600)

        self.MAX_IMAGE_MB = env_int("MAX_IMAGE_MB", 5)
        self.MAX_IMAGES_PER_PROPERTY = env_int("MAX_IMAGES_PER_PROPERTY", 8)

        self.ADMIN_EMAIL = env("ADMIN_EMAIL")
        self.ADMIN_PASSWORD = env("ADMIN_PASSWORD")
        self.ADMIN_NAME = env("ADMIN_NAME", "Site Admin")

        self.LOG_LEVEL = env("LOG_LEVEL", "INFO")
        self.INSTANCE_ID = env("INSTANCE_ID") or os.getenv("HOSTNAME", "local")

        for key, value in overrides.items():
            setattr(self, key, value)

    @property
    def is_production(self):
        return self.APP_ENV.lower() == "production"

    def validate(self):
        problems = []
        if self.is_production:
            if self.JWT_SECRET == DEV_JWT_SECRET or len(self.JWT_SECRET) < 32:
                problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
            if self.DATABASE_URL.startswith("sqlite"):
                problems.append("Production requires PostgreSQL (set DATABASE_URL or DB_HOST)")
        if self.STORAGE_BACKEND not in ("local", "s3"):
            problems.append("STORAGE_BACKEND must be 'local' or 's3'")
        if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET:
            problems.append("S3_BUCKET is required when STORAGE_BACKEND=s3")
        if problems:
            raise RuntimeError("Invalid configuration: " + "; ".join(problems))
