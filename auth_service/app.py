#!/usr/bin/env python3
from uuid import uuid4
from flask import Flask, request, jsonify
from datetime import datetime, timezone
from psycopg2 import pool
import time
import logging
import requests
import bcrypt
import psycopg2
import os
import json
import fcntl

app = Flask(__name__)
USER_SERVICE = os.environ.get("USER_SERVICE_URL", "http://localhost:5002")

# Logging of request data
class PandasHandler(logging.Handler):
    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename or os.environ.get(
            "METRICS_LOG_PATH", "/data/auth-requests.log")

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
                f.flush()
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
    port=int(os.environ.get("DB_PORT", 6432))
)

def get_connection():
    return connection_pool.getconn()

def release_connection(connection):
    connection_pool.putconn(connection)


@app.route('/auth', methods=['POST'])
def authenticate_user():
    """
    Fetch hasehed password from database and verify with bcrypt.
    """
    start_time = time.monotonic()

    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    propagated_headers = {"X-Request-ID": request_id}

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    # validate input
    if not username or not password:
        return jsonify({"error": "Missing credentials"}), 400

    # DB lookup for password
    conn = None
    cursor = None
    try:
        # POOL LOG TIMINING
        pool_start = time.monotonic()
        conn = get_connection()
        pool_ms = round((time.monotonic() - pool_start) * 1000, 3)
        cursor = conn.cursor()

        # DB LOG TIMING
        db_start = time.monotonic()
        cursor.execute(
            """
            SELECT
                password_hash
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        row = cursor.fetchone()
        db_ms = round((time.monotonic() - db_start) * 1000, 3)

        # close db connection
        cursor.close()
        release_connection(conn)
        conn = None
        cursor = None

        if not row:
            return jsonify({"error": "Not found"}), 404

        # BCRYPT LOG TIMING
        bcrypt_start = time.monotonic()

        stored_hash = row[0]
        password_ok = bcrypt.checkpw(
            password.encode(),
            stored_hash.encode()
        )

        bcrypt_ms = round((time.monotonic() - bcrypt_start) * 1000, 3)

        if not password_ok:
            return jsonify({"error": "Invalid credentials"}), 401

        # Call user-service
        user_service_start = time.monotonic()
        user_response = requests.post(
            f"{USER_SERVICE}/user",
            json={"username": username},
            headers=propagated_headers
        )
        user_response.raise_for_status()
        user_data = user_response.json()
        user_service_ms = round(
            (time.monotonic() - user_service_start) * 1000, 3)

        # Log timing
        total_ms = round((time.monotonic() - start_time) * 1000, 3)

        return jsonify({
            "status": "authenticated",
            "session_token": str(uuid4()),
            "user": user_data,
            "service_times": {
                "auth_pool_ms": pool_ms,
                "bcrypt_ms": bcrypt_ms,
                "auth_db_ms": db_ms,
                "user_service_call_ms": user_service_ms,
                "auth_ms": total_ms
            }
        }), 200

    except requests.RequestException as e:
        metrics_logger.error(json.dumps({
            "request_id": request_id,
            "event": "user_service_unavailable",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - start_time) * 1000, 3),
            "status": 502
        }))
        return jsonify({"error": "User service unavailable"}), 502

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
    return jsonify({"status": "ok", "service": "auth-service"}), 200
