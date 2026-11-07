"""RentEase application tier (Flask REST API)."""
import json
import logging
import sys
import time
import uuid

from flask import Flask, g, request

from .config import Config
from .db import Database, close_conn
from .errors import register_error_handlers
from .storage import create_storage


class JsonFormatter(logging.Formatter):
    """One JSON object per line on stdout, ready for CloudWatch / Loki / ELK."""

    def format(self, record):
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms", "user_id", "instance"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def configure_logging(level):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def create_app(config=None):
    cfg = config or Config()
    cfg.validate()
    configure_logging(cfg.LOG_LEVEL)

    app = Flask(__name__)
    app.config["RENTEASE"] = cfg
    app.config["MAX_CONTENT_LENGTH"] = (cfg.MAX_IMAGE_MB * cfg.MAX_IMAGES_PER_PROPERTY + 1) * 1024 * 1024
    app.json.sort_keys = False

    db = Database(cfg.DATABASE_URL, sslmode=cfg.DB_SSLMODE, pool_max=cfg.DB_POOL_MAX)
    app.extensions["rentease_db"] = db
    app.extensions["rentease_storage"] = create_storage(cfg)

    if cfg.AUTO_MIGRATE:
        db.migrate()

    register_error_handlers(app)
    app.teardown_appcontext(close_conn)

    from .routes.admin import bp as admin_bp
    from .routes.auth import bp as auth_bp
    from .routes.health import bp as health_bp
    from .routes.inquiries import bp as inquiries_bp
    from .routes.properties import bp as properties_bp

    for bp in (health_bp, auth_bp, properties_bp, inquiries_bp, admin_bp):
        app.register_blueprint(bp, url_prefix="/api")

    log = logging.getLogger("rentease.request")

    @app.before_request
    def start_request():
        g.start = time.perf_counter()
        g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]

    @app.after_request
    def finish_request(response):
        response.headers["X-Request-ID"] = g.get("request_id", "")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Served-By"] = cfg.INSTANCE_ID  # shows load balancing in demos

        origin = request.headers.get("Origin")
        if origin and origin in cfg.CORS_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Max-Age"] = "600"
            response.headers["Access-Control-Expose-Headers"] = "X-Served-By, X-Request-ID"

        if request.path != "/api/health":  # keep LB health checks out of the logs
            user = g.get("user")
            log.info(
                "request",
                extra={
                    "request_id": g.get("request_id"),
                    "method": request.method,
                    "path": request.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - g.get("start", time.perf_counter())) * 1000, 1),
                    "user_id": user["id"] if user else None,
                    "instance": cfg.INSTANCE_ID,
                },
            )
        return response

    @app.route("/api/<path:_any>", methods=["OPTIONS"])
    def cors_preflight(_any):
        return "", 204

    with app.app_context():
        from .bootstrap import ensure_admin

        ensure_admin()

    return app
