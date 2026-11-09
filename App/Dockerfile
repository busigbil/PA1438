FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir psycopg2-binary flask requests pandas gunicorn python-json-logger bcrypt concurrent-log-handler

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--workers=4", "--threads=6", "--worker-class=gthread", "--timeout=30", "--graceful-timeout=10", "--bind=0.0.0.0:5000", "app:app", "--html"]
