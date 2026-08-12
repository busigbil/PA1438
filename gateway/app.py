from flask import Flask, request, render_template, session, redirect, url_for, jsonify, g
from datetime import datetime, timezone
import requests
import uuid
import time
import logging
import os
import json
import logging
import fcntl

app = Flask(__name__)
app.secret_key = "dev-secret-key" 
AUTH_SERVICE = os.environ.get("AUTH_SERVICE_URL", "http://localhost:5001")

# Logging of requesst data
class PandasHandler(logging.Handler):
    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename or os.environ.get(
            "METRICS_LOG_PATH", "/data/gateway-requests.log")

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

# Log execution times for each path
@app.before_request
def start_timer():
    g.start_time = time.monotonic()
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

@app.after_request
def log_request(response):
    duration_ms = round((time.monotonic() - g.start_time) * 1000, 3)
    metrics_logger.info(json.dumps({
        "request_id": g.get("request_id"),
        "event": "request_timing",
        "endpoint": request.endpoint,
        "path": request.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    }))
    return response


@app.route('/')
def index():
    """
    Render login-form.
    """
    return render_template('login.html'), 200

@app.route('/home')
def home():
    """
    Render users home-page when logged in.
    """
    if not session.get("is_authenticated"):
        return redirect(url_for('index'))

    render_start = time.monotonic()
    html = render_template('home.html', user=session.get("username"))
    render_ms = round((time.monotonic() - render_start) * 1000, 3)

    metrics_logger.info(json.dumps({
        "request_id": g.get("request_id"),
        "event": "home_render",
        "render_ms": render_ms,
    }))
    return html, 200


@app.route('/login', methods=['POST'])
def login():
    """
    Perform login functions and log the returned data from all services.
    """

    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        return render_template('login.html', error="Authentication failed"), 400

    headers = {"X-Request-ID": g.request_id}

    metrics_logger.info(json.dumps({
        "request_id": g.request_id,
        "event": "login_attempt",
        "username": username,
    }))

    # CALL AUTH SERVICE
    try:
        auth_service_start = time.monotonic()
        auth_response = requests.post(
            f"{AUTH_SERVICE}/auth",
            json={
                "username": username,
                "password": password
            },
            headers=headers
        )
        auth_response.raise_for_status()
        auth_data = auth_response.json()
        auth_service_ms = round(
            (time.monotonic() - auth_service_start) * 1000, 3)

        # add data to session
        session["token"] = auth_data["session_token"]
        session["is_authenticated"] = True
        session["username"] = auth_data["user"]["username"]
        session["user_id"] = auth_data["user"]["user_id"]
        session["login_request_id"] = g.request_id

        svc_times = auth_data.get("service_times", {})
        user_times = auth_data.get("user", {}).get("service_times", {})

        # Log all collected data
        total_ms = round((time.monotonic() - g.start_time) * 1000, 3)
        metrics_logger.info(json.dumps({
            "request_id":      g.request_id,
            "event":           "login_success",
            "username":        username,
            "total_ms":        total_ms,
            "gateway_request_ms": auth_service_ms,
            "auth_ms":         svc_times.get("auth_ms"),
            "auth_pool_ms":    svc_times.get("auth_pool_ms"),
            "auth_db_ms":      svc_times.get("auth_db_ms"),
            "auth_bcrypt_ms":  svc_times.get("bcrypt_ms"),
            "auth_request_ms": svc_times.get("user_service_call_ms"),
            "user_ms":         user_times.get("user_ms"),
            "user_pool_ms":    user_times.get("user_pool_ms"),
            "user_select_ms":  user_times.get("user_select_ms"),
            "user_update_ms":  user_times.get("user_update_ms"),
        }))
        return redirect(url_for('home')), 302

    except requests.RequestException as e:
        metrics_logger.error(json.dumps({
            "request_id": g.request_id,
            "event": "Authentication_failed",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - g.start_time) * 1000, 3),
            "status": 502
        }))
        return render_template('login.html', error="Authentication failed"), 502

    except Exception as e:
        metrics_logger.error(json.dumps({
            "request_id": g.request_id,
            "event": "unhandled_error",
            "username": username,
            "error": str(e),
            "total_ms": round((time.monotonic() - g.start_time) * 1000, 3),
            "status": 500
        }))
        return render_template('login.html', error="Internal error"), 500


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index')), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "gateway"}), 200
