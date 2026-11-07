"""Health endpoints for load balancer target groups and container orchestrators.

* /api/health      - liveness + database connectivity (use as the ALB health check)
* /api/health/live - process is up, no dependencies (Kubernetes livenessProbe)
"""
from flask import Blueprint, current_app, jsonify

from ..db import query

bp = Blueprint("health", __name__)


@bp.get("/health/live")
def live():
    return jsonify({"status": "ok"})


@bp.get("/health")
def health():
    cfg = current_app.config["RENTEASE"]
    checks = {}
    healthy = True
    try:
        query("SELECT 1 AS ok", one=True)
        checks["database"] = "ok"
    except Exception as exc:  # report, do not crash
        current_app.logger.warning("Health check: database unavailable: %s", exc)
        checks["database"] = "unavailable"
        healthy = False
    body = {
        "status": "ok" if healthy else "degraded",
        "instance": cfg.INSTANCE_ID,
        "storage": cfg.STORAGE_BACKEND,
        "checks": checks,
    }
    return jsonify(body), (200 if healthy else 503)
