#!/usr/bin/env bash
# Captain Taxi — VPS deploy script
# Run on Hostinger VPS: bash scripts/deploy.sh
set -euo pipefail

echo "==> Pulling latest code..."
git pull origin main

echo "==> Copying env file (skip if already exists)..."
[ -f .env ] || cp .env.example .env && echo "  -> Created .env from template — fill in secrets before continuing!" && exit 1

echo "==> Building Docker images..."
docker compose build orchestrator

echo "==> Running database migrations..."
docker compose run --rm orchestrator alembic upgrade head

echo "==> Restarting orchestrator..."
docker compose up -d orchestrator

echo "==> Done. Orchestrator running on :8000"
docker compose ps
