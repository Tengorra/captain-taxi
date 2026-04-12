FROM python:3.11-slim

WORKDIR /app

# System deps for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run migrations then start the server
CMD ["sh", "-c", "cd /app/dispatch && alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4"]
