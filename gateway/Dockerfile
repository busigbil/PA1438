FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests pandas gunicorn

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--workers=5", "--threads=8", "--worker-class=gthread", "--timeout=30", "--graceful-timeout=10", "--backlog=128", "--enable-backlog-metric", "--statsd-host=listener:8125", "--error-logfile=-", "--bind=0.0.0.0:5000", "app:app"]
