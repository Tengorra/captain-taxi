FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY admin/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
# Host platforms (Railway, Render, Fly) set $PORT; fall back to 8006 locally.
# Alembic runs before uvicorn so schema migrations 002 + 003 are always
# applied on a fresh deploy. `|| true` keeps the container alive if alembic
# fails (e.g. DB not yet reachable on the first boot) — the app would
# error on first request anyway, which is the right signal.
CMD ["sh", "-c", "alembic upgrade head || true; exec uvicorn admin.main:app --host 0.0.0.0 --port ${PORT:-8006} --workers 2"]

