FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary bcrypt requests pandas gunicorn

COPY app.py .

EXPOSE 5001

CMD ["gunicorn", "--workers=5", "--threads=3", "--worker-class=gthread", "--error-logfile=-", "--bind=0.0.0.0:5001", "app:app"]