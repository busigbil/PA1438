import psycopg2
from psycopg2 import pool
import os
import time

# Database connection configuration
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    minconn=24,
    maxconn=24,
    database="users_db",
    user="postgres",
    password="postgres",
    host=os.environ.get('DATABASE_HOST', 'localhost'),
    port=5432
)


def get_connection():
    return connection_pool.getconn()

def release_connection(connection):
    connection_pool.putconn(connection)

def calc_time(timing):
    return round((time.perf_counter() - timing) * 1000, 3)



def get_user_from_db(username):
    """Connect to the database and fetch user information."""
    pool_start = time.perf_counter()
    conn = get_connection()
    pool_ms = calc_time(pool_start)

    query_start = time.perf_counter()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    username,
                    name,
                    password_hash,
                    last_login
                FROM users
                WHERE username = %s
                        """,
                (username,)
            )
            row = cursor.fetchone()
    finally:
        # close db connection
        cursor.close()
        release_connection(conn)
    query_ms = calc_time(query_start)

    return row, pool_ms, query_ms


def update_timestamp_db(user_id):
    """Connect to the database and update user record with login-timestamp."""
    
    pool_start = time.perf_counter()
    conn = get_connection()
    pool_ms = calc_time(pool_start)

    query_start = time.perf_counter()
    try:
        with conn.cursor() as cursor:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login = NOW() WHERE id = %s",
                (user_id,)
            )
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        # close db connection
        cursor.close()
        release_connection(conn)
    query_ms = calc_time(query_start)

    return pool_ms, query_ms
