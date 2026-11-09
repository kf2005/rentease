"""Thin database layer.

Production uses PostgreSQL (e.g. Amazon RDS) through a psycopg2 connection
pool. SQLite is supported only for quick local development and the automated
tests. Queries are written once with ``%s`` placeholders and portable SQL.
"""
import os
import sqlite3
import threading
from datetime import datetime

from flask import current_app, g

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")
MIGRATION_LOCK_ID = 7_340_291  # arbitrary constant for pg_advisory_lock


class Database:
    def __init__(self, url, sslmode=None, pool_max=10):
        self.url = url
        self.sslmode = sslmode
        self.pool_max = pool_max
        self._pool = None
        self._pool_pid = None
        self._lock = threading.Lock()
        if url.startswith("sqlite:///"):
            self.kind = "sqlite"
            self.sqlite_path = url[len("sqlite:///"):]
        elif url.startswith(("postgres://", "postgresql://")):
            self.kind = "postgres"
        else:
            raise RuntimeError("Unsupported DATABASE_URL scheme")

    # -- connections -------------------------------------------------------
    def _get_pool(self):
        # Created lazily and per process so it is safe with gunicorn's
        # pre-fork workers (connections must not be shared across forks).
        if self._pool is None or self._pool_pid != os.getpid():
            with self._lock:
                if self._pool is None or self._pool_pid != os.getpid():
                    from psycopg2.pool import ThreadedConnectionPool

                    kwargs = {"connect_timeout": 5}
                    if self.sslmode:
                        kwargs["sslmode"] = self.sslmode
                    self._pool = ThreadedConnectionPool(1, self.pool_max, self.url, **kwargs)
                    self._pool_pid = os.getpid()
        return self._pool

    def connect(self):
        if self.kind == "sqlite":
            conn = sqlite3.connect(self.sqlite_path, timeout=10)
            conn.row_factory = _dict_factory
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        return self._get_pool().getconn()

    def release(self, conn, broken=False):
        if self.kind == "sqlite":
            conn.close()
            return
        try:
            conn.rollback()
        except Exception:  # connection already dead (e.g. DB failover)
            broken = True
        self._get_pool().putconn(conn, close=broken)

    def cursor(self, conn):
        if self.kind == "sqlite":
            return conn.cursor()
        from psycopg2.extras import RealDictCursor

        return conn.cursor(cursor_factory=RealDictCursor)

    def adapt(self, sql):
        return sql.replace("%s", "?") if self.kind == "sqlite" else sql

    # -- schema ------------------------------------------------------------
    def migrate(self):
        path = os.path.join(SCHEMA_DIR, f"schema.{self.kind}.sql")
        with open(path, "r", encoding="utf-8") as fh:
            statements = [s.strip() for s in fh.read().split(";") if s.strip()]
        conn = self.connect()
        try:
            cur = self.cursor(conn)
            if self.kind == "postgres":
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
            for statement in statements:
                cur.execute(statement)
            conn.commit()  # lock is released here, after the schema is visible
        finally:
            self.release(conn)  # rolls back on error, which also releases the lock


def _dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# -- request-scoped helpers ------------------------------------------------
def get_db():
    return current_app.extensions["rentease_db"]


def get_conn():
    if "db_conn" not in g:
        g.db_conn = get_db().connect()
    return g.db_conn


def close_conn(exc=None):
    conn = g.pop("db_conn", None)
    if conn is not None:
        broken = False
        if exc is not None:
            broken = _is_connection_error(exc)
        get_db().release(conn, broken=broken)


def _is_connection_error(exc):
    try:
        import psycopg2

        return isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))
    except ImportError:
        return False


def query(sql, params=(), one=False):
    db = get_db()
    cur = db.cursor(get_conn())
    cur.execute(db.adapt(sql), tuple(params))
    rows = cur.fetchall()
    rows = [normalise(r) for r in rows]
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, params=(), returning=False):
    """Run an INSERT/UPDATE/DELETE. With returning=True, return first row."""
    db = get_db()
    cur = db.cursor(get_conn())
    cur.execute(db.adapt(sql), tuple(params))
    if returning:
        rows = cur.fetchall()  # exhaust the cursor so commit() is always safe
        return normalise(rows[0]) if rows else None
    return cur.rowcount


def commit():
    get_conn().commit()


def normalise(row):
    if row is None:
        return None
    out = {}
    for key, value in dict(row).items():
        if isinstance(value, datetime):
            value = value.isoformat()
        out[key] = value
    return out


def is_unique_violation(exc):
    if isinstance(exc, sqlite3.IntegrityError) and "UNIQUE" in str(exc):
        return True
    try:
        import psycopg2.errors

        return isinstance(exc, psycopg2.errors.UniqueViolation)
    except ImportError:
        return False
