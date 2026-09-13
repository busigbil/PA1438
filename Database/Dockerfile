FROM python:3.11-slim 

WORKDIR /seed 

RUN pip install --no-cache-dir psycopg2-binary bcrypt faker 

COPY seed.py . 

CMD ["python3", "seed.py"]