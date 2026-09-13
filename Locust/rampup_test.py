# locustfile.py
import random
import psycopg2
import os
from locust import HttpUser, task, between, LoadTestShape


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
    Send login-requests for each route.
    """
    host = HOST_URL
    wait_time = between(1, 5)

    def on_start(self):
        self.username = random.choice(USERNAMES)

    @task
    def login(self):
        self.client.get("/")
        self.client.post("/login", data={
            "username": self.username,
            "password": "Test1234!"
        })
        self.client.get("/home")


class StepLoadShape(LoadTestShape):
    """
    Load test shape with different user and spawn rate at different stages.
    """

    stages = [
        {"duration": 95, "users": 5, "spawn_rate": 1},
        {"duration": 190, "users": 50, "spawn_rate": 9},
        {"duration": 285, "users": 100, "spawn_rate": 10},
        {"duration": 385, "users": 500, "spawn_rate": 40},
        {"duration": 485, "users": 1000, "spawn_rate": 50},
        {"duration": 585, "users": 2000, "spawn_rate": 100},
        {"duration": 685, "users": 3000, "spawn_rate": 100},
        {"duration": 785, "users": 4000, "spawn_rate": 100},
        {"duration": 885, "users": 5000, "spawn_rate": 100},
        {"duration": 985, "users": 6000, "spawn_rate": 100},
        {"duration": 1080, "users": 6250, "spawn_rate": 50},
        {"duration": 1175, "users": 6500, "spawn_rate": 50},
    ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]

        return None
