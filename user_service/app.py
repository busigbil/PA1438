#!/usr/bin/env python3
import time
import logging
import psycopg2
import os
import json
from uuid import uuid4
from flask import Flask, request, jsonify
from psycopg2 import pool
from datetime import datetime, timezone
import fcntl

app = Flask(__name__)

# Logging of request data
class PandasHandler(logging.Handler):
    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename or os.environ.get(
            "METRICS_LOG_PATH", "/data/user-requests.log")

    def emit(self, record):
        try:
            data = json.loads(record.getMessage())
        except Exception:
            data = {"raw_message": record.getMessage(), "parse_error": True}

        data["service"] = os.environ.get("SERVICE_NAME", "unknown")
        data["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc).isoformat()
        data["level"] = record.levelname

        with open(self.filename, "a", buffering=1) as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

logging.basicConfig(level=logging.INFO)
metrics_logger = logging.getLogger("metrics")
metrics_logger.addHandler(PandasHandler())
metrics_logger.setLevel(logging.INFO)
metrics_logger.propagate = False

# Database connection configuration
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=os.environ.get("DB_HOST", "pgbouncer"),
    database=os.environ.get("DB_NAME", "users_db"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "postgres"),
    port=int(os.environ.get("DB_PORT", 5432))
)

def get_connection():
    return connection_pool.getconn()

def release_connection(connection):
    connection_pool.putconn(connection)


@app.route('/user', methods=['POST'])
def get_user():
    """
    Looks up the user by username.
    Returns user profile data.
    """
    start_time = time.monotonic()

    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    data = request.get_json() or {}
    username = data.get("username")

    # validate input
    if not username:
        return jsonify({"error": "Missing credentials"}), 400

    # DB lookup
    conn = None
    cursor = None
    try:
        # POOL LOG TIMINING
        pool_start = time.monotonic()
        conn = get_connection()
        pool_ms = round((time.monotonic() - pool_start) * 1000, 3)
        cursor = conn.cursor()

        # SELECT LOG TIMING
        select_start = time.monotonic()
        cursor.execute(
            """
            SELECT
                id,
                username,
                name,
                last_login
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        row = cursor.fetchone()
        select_ms = round((time.monotonic() - select_start) * 1000, 3)

        if not row:
            return jsonify({"error": "Not found"}), 404

        (user_id, db_username, db_name, last_login) = row

        # UPDATE LOG TIMING
        update_start = time.monotonic()
        cursor.execute(
            "UPDATE users SET last_login = NOW() WHERE id = %s",
            (user_id,)
        )
        conn.commit()
        update_ms = round((time.monotonic() - update_start) * 1000, 3)

        # close db connection
        cursor.close()
        release_connection(conn)
        conn = None
        cursor = None

        # LOG TOTAL TIME
        total_ms = round((time.monotonic() - start_time) * 1000, 3)

        return jsonify({
            "user_id": user_id,
            "username": db_username,
            "name": db_name,
            "last_login": str(last_login),
            "service_times": {
                "user_pool_ms": pool_ms,
                "user_select_ms": select_ms,
                "user_update_ms": update_ms,
                "user_ms": total_ms
            }
        }), 200

    except psycopg2.OperationalError as e:
        metrics_logger.error(json.dumps({
            "request_id": request_id,
            "event": "database_unavailable",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - start_time) * 1000, 3),
            "status": 503
        }))
        return jsonify({"error": "Database unavailable"}), 503
    
    except psycopg2.pool.PoolError as e:
        metrics_logger.error(json.dumps({
            "request_id": request_id,
            "event": "pool_exhausted",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - start_time) * 1000, 3),
            "status": 503
        }))
        return jsonify({"error": "Database pool exhausted"}), 503
    
    except Exception as e:
        metrics_logger.error(json.dumps({
            "request_id": request_id,
            "event": "unhandled_error",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - start_time) * 1000, 3),
            "status": 500
        }))
        return jsonify({"error": "Internal error"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            release_connection(conn)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "user-service"}), 200

