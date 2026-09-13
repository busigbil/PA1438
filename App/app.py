from database_functions import get_user_from_db, update_timestamp_db
from flask import Flask, request, render_template, session, redirect, url_for, jsonify, g
from pythonjsonlogger.json import JsonFormatter
from concurrent_log_handler import ConcurrentRotatingFileHandler
import uuid
import time
import logging
import bcrypt
import os

app = Flask(__name__)
app.secret_key = "secret-key"

# Logging of request data
logger = logging.getLogger("app")
logger.setLevel(logging.INFO)
logger.propagate = False

logfile = os.path.abspath('/data/app_log.jsonl')
rotateHandler = ConcurrentRotatingFileHandler(logfile, "a", 512*1024, 5)

# handler = logging.FileHandler('/data/app_log.jsonl')
rotateHandler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s"))
logger.addHandler(rotateHandler)

# Log execution times for each path


@app.before_request
def before_request():
    g.start_time = time.monotonic()
    g.timestamp = time.time()
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def log_request(response):
    duration_ms = round((time.monotonic() - g.start_time) * 1000, 3)
    logger.info({
        "timestamp": g.timestamp,
        "request_id": g.request_id,
        "event": "request_times",
        "path": request.path,
        "status_code": response.status_code,
        "duration_ms": duration_ms,
    })
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
        logger.error({
            "request_id": g.request_id,
            "event": "home_failed",
        })
        return redirect(url_for('index'))

    html = render_template('home.html', name=session.get("name"))
    return html, 200


@app.route('/login', methods=['POST'])
def login():
    """
    Perform login functions and log data from individual parts.
    """
    username = request.form.get("username")
    password = request.form.get("password")

    if not username or not password:
        logger.error({
            "request_id": g.request_id,
            "event": "login_failed",
        })
        return render_template('login.html', error="Authentication failed"), 400

    user_row, select_wait_ms, select_query_ms = get_user_from_db(username)

    if not user_row:
        logger.error({
            "request_id":      g.request_id,
            "event":           "login_failed",
            "select_wait_ms": select_wait_ms,
            "select_db_ms": select_query_ms,
        })
        return jsonify({"error": "Not found"}), 404

    # Bcrypt log timing
    bcrypt_start = time.monotonic()
    stored_hash = user_row[3]
    password_ok = bcrypt.checkpw(
        password.encode(),
        stored_hash.encode()
    )
    bcrypt_ms = round((time.monotonic() - bcrypt_start) * 1000, 3)

    if not password_ok:
        logger.error({
            "request_id":      g.request_id,
            "event":           "login_failed",
            "select_wait_ms": select_wait_ms,
            "select_db_ms": select_query_ms,
            "bcrypt_ms": bcrypt_ms,
        })
        return jsonify({"error": "Invalid credentials"}), 401

    user_id = user_row[0]
    update_wait_ms, update_query_ms = update_timestamp_db(user_id)

    # Add data to session
    session["token"] = str(uuid.uuid4())
    session["is_authenticated"] = True
    session["name"] = user_row[2]
    session["login_request_id"] = g.request_id

    # Log collected data
    logger.info({
        "request_id": g.request_id,
        "event": "login_success",
        "select_wait_ms": select_wait_ms,
        "select_db_ms": select_query_ms,
        "bcrypt_ms": bcrypt_ms,
        "update_wait_ms": update_wait_ms,
        "update_query_ms": update_query_ms,
    })
    return redirect(url_for('home')), 302


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "app"}), 200
