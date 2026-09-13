# locustfile.py
import random
import psycopg2
import time
import uuid
import os
import json
from locust import HttpUser, task, between, events


# Load users from database
def load_users():
    conn = psycopg2.connect(
        database="users_db",
        user="postgres",
        password="postgres",
        host=os.environ.get('DATABASE_HOST', 'localhost'),
        port=5432
    )
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row[0] for row in rows]


HOST_URL = os.environ.get("HOST_URL", "http://localhost:5000")
USERNAMES = load_users()


class LoginUser(HttpUser):
    """
    Send login-requests and log request-data for each route.
    """
    host = HOST_URL
    wait_time = between(1, 5)

    def on_start(self):
        self.username = random.choice(USERNAMES)

    @task
    def login(self):
        request_id = str(uuid.uuid4())
        headers = {"X-Request-ID": request_id}
        start_time = time.time()

        context = {
            "start_time": start_time,
            "request_id": request_id,
        }

        # Measure render login page: GET /
        with self.client.get("/",
                             headers=headers,
                             name="/",
                             catch_response=True,
                             context=context,
                             ) as index_response:
            if index_response.status_code == 200:
                index_response.success()
            else:
                error_detail = str(
                    getattr(index_response, 'error', None) or index_response.text[:100])
                index_response.failure(
                    f"Index failed - status {index_response.status_code}: {error_detail}")

        # Measure login: POST /login
        with self.client.post("/login", data={
            "username": self.username,
            "password": "Test1234!"
        },
            headers=headers,
            allow_redirects=False,
            catch_response=True,
            context=context,
        ) as login_response:
            if login_response.status_code == 302:
                login_response.success()
            else:
                error_detail = str(
                    getattr(login_response, 'error', None) or login_response.text[:100])
                login_response.failure(
                    f"Login failed - status {login_response.status_code}: {error_detail}")

        # Measure render user page: GET /home
        with self.client.get("/home",
                             headers=headers,
                             name="/home",
                             catch_response=True,
                             context=context,
                             ) as home_response:
            if home_response.status_code == 200:
                home_response.success()
            else:
                error_detail = str(
                    getattr(home_response, 'error', None) or home_response.text[:100])
                home_response.failure(
                    f"Home failed - status {home_response.status_code}: {error_detail}")
            self.client.cookies.clear()



### LOG REQUEST DATA ###

RESULTS_PATH = "/data/locust_log.jsonl"
results = []


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response,
               context, exception, start_time, **kwargs):
    """
    Event handler that get triggered on every request.
    """
    results.append({
        "timestamp": context.get("start_time"),
        "start_time": start_time,
        "request_id": context.get("request_id"),
        "path": name,
        "response_time_ms": response_time,
        "exception": str(exception) if exception else None,
    })


@events.report_to_master.add_listener
def on_report_to_master(client_id, data):
    """
    This event is triggered on the worker instances every time results
    to be sent to the locust master.
    """
    data["results"] = results.copy()
    results.clear()


@events.worker_report.add_listener
def on_worker_report(client_id, data):
    """
    This event is triggered on the master instance when new results arrives
    from a worker.
    """
    batch = data["results"]
    if not batch:
        return
    with open(RESULTS_PATH, "a") as f:
        for entry in batch:
            f.write(json.dumps(entry) + "\n")


@events.test_stop.add_listener
def save_remaining(environment, **kwargs):
    """
    Write last results to file when test ends.
    """
    is_worker = environment.parsed_options and getattr(environment.parsed_options, "worker", False)
    if is_worker or not results:
        return  # workers ska aldrig skriva direkt till fil
    with open(RESULTS_PATH, "a") as f:
        for entry in results:
            f.write(json.dumps(entry) + "\n")
    results.clear()
