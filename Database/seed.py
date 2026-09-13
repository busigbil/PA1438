from faker import Faker
import psycopg2
import bcrypt

conn = psycopg2.connect(
    database="users_db",
    user="postgres",
    password="postgres",
    host="db",
    port=5432
)
cursor = conn.cursor()

# Check if database is allready seeded, and exit script
cursor.execute("""SELECT COUNT(*) FROM users;""")
count = cursor.fetchone()
if count[0] > 1000:
    cursor.close()
    conn.close()
    print("Database is already seeded.")
    exit()

num_records = 5000
records = []
fake = Faker("sv_SE")

for _ in range(num_records):
    username = fake.user_name()
    password = "Test1234!"
    password_hash = bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(rounds=6)
    ).decode()
    name = fake.name()

    records.append((username, password_hash, name))

# SQL-query with placeholders
query = """
            INSERT INTO users (username, password_hash, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        """

# Execute SQL-query with all values
cursor.executemany(query, records)

# Commit transaction
conn.commit()
cursor.close()
conn.close()
print("Data inserted into database.")
exit()
