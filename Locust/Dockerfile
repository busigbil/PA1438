FROM python:3.11-slim

WORKDIR /locust

RUN pip install --no-cache-dir psycopg2-binary locust

COPY locustfile.py .

EXPOSE 8089

CMD ["locust", "-f", "locustfile.py", "--processes", "-1"]