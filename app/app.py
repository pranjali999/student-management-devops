"""
Student Management System - Flask REST API + web UI.

Built to be a good *DevOps target*:
  * /health   -> liveness/readiness probe (Docker, Kubernetes, CI smoke test)
  * /metrics  -> Prometheus text format (scraped by Prometheus, shown in Grafana)
  * 12-factor config via environment variables (DATABASE_URL, APP_VERSION, ...)
  * SQLite by default (zero setup), PostgreSQL when DATABASE_URL is set
"""
import os
import re
import sqlite3
import threading
import time

from flask import Flask, g, jsonify, render_template, request

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    course TEXT NOT NULL,
    year INTEGER NOT NULL
)
"""
POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    course TEXT NOT NULL,
    year INTEGER NOT NULL
)
"""


class Metrics:
    """Tiny thread-safe Prometheus exporter (no external dependency)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.requests = {}       # (method, endpoint, status) -> count
        self.latency_sum = {}    # (method, endpoint) -> seconds
        self.latency_count = {}  # (method, endpoint) -> count

    def observe(self, method, endpoint, status, seconds):
        with self.lock:
            k = (method, endpoint, str(status))
            self.requests[k] = self.requests.get(k, 0) + 1
            k2 = (method, endpoint)
            self.latency_sum[k2] = self.latency_sum.get(k2, 0.0) + seconds
            self.latency_count[k2] = self.latency_count.get(k2, 0) + 1

    def render(self, students_total, version, uptime):
        lines = [
            "# HELP sms_http_requests_total Total HTTP requests.",
            "# TYPE sms_http_requests_total counter",
        ]
        with self.lock:
            for (m, e, s), v in sorted(self.requests.items()):
                lines.append(
                    f'sms_http_requests_total{{method="{m}",endpoint="{e}",status="{s}"}} {v}')
            lines += [
                "# HELP sms_http_request_duration_seconds_sum Total time spent serving requests.",
                "# TYPE sms_http_request_duration_seconds_sum counter",
            ]
            for (m, e), v in sorted(self.latency_sum.items()):
                lines.append(
                    f'sms_http_request_duration_seconds_sum{{method="{m}",endpoint="{e}"}} {v:.6f}')
            lines += [
                "# HELP sms_http_request_duration_seconds_count Number of timed requests.",
                "# TYPE sms_http_request_duration_seconds_count counter",
            ]
            for (m, e), v in sorted(self.latency_count.items()):
                lines.append(
                    f'sms_http_request_duration_seconds_count{{method="{m}",endpoint="{e}"}} {v}')
        lines += [
            "# HELP sms_students_total Number of students stored in the database.",
            "# TYPE sms_students_total gauge",
            f"sms_students_total {students_total}",
            "# HELP sms_app_info Application version information.",
            "# TYPE sms_app_info gauge",
            f'sms_app_info{{version="{version}"}} 1',
            "# HELP sms_uptime_seconds Seconds since the app started.",
            "# TYPE sms_uptime_seconds gauge",
            f"sms_uptime_seconds {uptime:.0f}",
        ]
        return "\n".join(lines) + "\n"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        SQLITE_PATH=os.environ.get("SQLITE_PATH", "students.db"),
        APP_VERSION=os.environ.get("APP_VERSION", "dev"),
    )
    if test_config:
        app.config.update(test_config)

    metrics = Metrics()
    started = time.time()
    use_pg = bool(app.config["DATABASE_URL"])

    # ------------------------------------------------------------------ DB
    def get_db():
        if "db" not in g:
            if use_pg:
                import psycopg2
                import psycopg2.extras
                g.db = psycopg2.connect(
                    app.config["DATABASE_URL"],
                    cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                g.db = sqlite3.connect(app.config["SQLITE_PATH"])
                g.db.row_factory = sqlite3.Row
        return g.db

    def run(sql, params=(), fetch=None, commit=False):
        """Run one statement. fetch = 'one' | 'all' | None."""
        db = get_db()
        if use_pg:
            sql = sql.replace("?", "%s")
        cur = db.cursor()
        try:
            cur.execute(sql, params)
            result = None
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            if commit:
                db.commit()
            return result, cur
        except Exception:
            db.rollback()
            raise

    def init_db():
        db = get_db()
        cur = db.cursor()
        cur.execute(POSTGRES_SCHEMA if use_pg else SQLITE_SCHEMA)
        db.commit()

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        init_db()

    # ------------------------------------------------------------ helpers
    def validate(data, partial=False):
        errors = []
        if not isinstance(data, dict):
            return None, ["JSON body required"]
        clean = {}
        for field in ("name", "email", "course"):
            if field in data or not partial:
                val = str(data.get(field, "")).strip()
                if not val:
                    errors.append(f"{field} is required")
                clean[field] = val
        if clean.get("email") and not EMAIL_RE.match(clean["email"]):
            errors.append("email is not valid")
        if "year" in data or not partial:
            try:
                year = int(data.get("year"))
                if not 1 <= year <= 6:
                    raise ValueError
                clean["year"] = year
            except (TypeError, ValueError):
                errors.append("year must be a number between 1 and 6")
        return clean, errors

    def row(r):
        return {k: r[k] for k in ("id", "name", "email", "course", "year")}

    def email_taken(email, exclude_id=None):
        r, _ = run("SELECT id FROM students WHERE email = ?", (email,), fetch="one")
        return r is not None and r["id"] != exclude_id

    # ----------------------------------------------------- request metrics
    @app.before_request
    def start_timer():
        g.t0 = time.perf_counter()

    @app.after_request
    def record(resp):
        if request.endpoint and request.endpoint != "static":
            endpoint = request.url_rule.rule if request.url_rule else request.endpoint
            if endpoint != "/metrics":
                metrics.observe(request.method, endpoint, resp.status_code,
                                time.perf_counter() - g.get("t0", time.perf_counter()))
        return resp

    # -------------------------------------------------------------- routes
    @app.get("/")
    def index():
        return render_template("index.html", version=app.config["APP_VERSION"])

    @app.get("/health")
    def health():
        try:
            run("SELECT 1", fetch="one")
            return jsonify(status="ok", version=app.config["APP_VERSION"]), 200
        except Exception as exc:  # noqa: BLE001
            return jsonify(status="unhealthy", error=str(exc)), 503

    @app.get("/metrics")
    def prometheus_metrics():
        try:
            r, _ = run("SELECT COUNT(*) AS c FROM students", fetch="one")
            total = r["c"]
        except Exception:  # noqa: BLE001
            total = -1
        body = metrics.render(total, app.config["APP_VERSION"], time.time() - started)
        return body, 200, {"Content-Type": "text/plain; version=0.0.4"}

    @app.get("/api/students")
    def list_students():
        q = request.args.get("q", "").strip()
        if q:
            like = f"%{q.lower()}%"
            rows, _ = run(
                "SELECT * FROM students WHERE LOWER(name) LIKE ? OR LOWER(course) LIKE ? "
                "OR LOWER(email) LIKE ? ORDER BY id", (like, like, like), fetch="all")
        else:
            rows, _ = run("SELECT * FROM students ORDER BY id", fetch="all")
        return jsonify([row(r) for r in rows])

    @app.post("/api/students")
    def create_student():
        clean, errors = validate(request.get_json(silent=True))
        if errors:
            return jsonify(errors=errors), 400
        if email_taken(clean["email"]):
            return jsonify(errors=["email already registered"]), 409
        sql = "INSERT INTO students (name, email, course, year) VALUES (?, ?, ?, ?)"
        params = (clean["name"], clean["email"], clean["course"], clean["year"])
        if use_pg:
            res, _ = run(sql + " RETURNING id", params, fetch="one", commit=True)
            new_id = res["id"]
        else:
            _, cur = run(sql, params, commit=True)
            new_id = cur.lastrowid
        clean["id"] = new_id
        return jsonify(clean), 201

    @app.get("/api/students/<int:sid>")
    def get_student(sid):
        r, _ = run("SELECT * FROM students WHERE id = ?", (sid,), fetch="one")
        if r is None:
            return jsonify(errors=["student not found"]), 404
        return jsonify(row(r))

    @app.put("/api/students/<int:sid>")
    def update_student(sid):
        existing, _ = run("SELECT * FROM students WHERE id = ?", (sid,), fetch="one")
        if existing is None:
            return jsonify(errors=["student not found"]), 404
        clean, errors = validate(request.get_json(silent=True), partial=True)
        if errors:
            return jsonify(errors=errors), 400
        merged = {**row(existing), **clean}
        if email_taken(merged["email"], exclude_id=sid):
            return jsonify(errors=["email already registered"]), 409
        run("UPDATE students SET name=?, email=?, course=?, year=? WHERE id=?",
            (merged["name"], merged["email"], merged["course"], merged["year"], sid),
            commit=True)
        return jsonify(merged)

    @app.delete("/api/students/<int:sid>")
    def delete_student(sid):
        _, cur = run("DELETE FROM students WHERE id = ?", (sid,), commit=True)
        if cur.rowcount == 0:
            return jsonify(errors=["student not found"]), 404
        return "", 204

    return app


# gunicorn entrypoint: `gunicorn app.app:app` (module path from project root)
app = create_app() if os.environ.get("CREATE_APP_ON_IMPORT", "1") == "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
