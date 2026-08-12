FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary pandas gunicorn

COPY app.py .

EXPOSE 5002

CMD ["gunicorn", "--workers=6", "--threads=4", "--worker-class=gthread", "--error-logfile=-", "--bind=0.0.0.0:5002", "app:app"]
