#!/bin/bash
# Captain Taxi — Full Stack Deployment Script
# Run on your Hostinger VPS (82.29.178.157) as root
# Usage: bash deploy.sh

set -e
echo "========================================="
echo "  Captain Taxi — Full Deployment"
echo "========================================="

# 1. Install Docker & Docker Compose if not present
if ! command -v docker &> /dev/null; then
    echo "[1] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "[1] Docker already installed."
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "[1b] Installing Docker Compose..."
    apt-get install -y docker-compose-plugin
fi

# 2. Create SSL directory placeholder (replace with real certs later)
mkdir -p /root/captain-taxi/ssl
if [ ! -f /root/captain-taxi/ssl/fullchain.pem ]; then
    echo "[2] Creating self-signed SSL cert (replace with Let's Encrypt later)..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /root/captain-taxi/ssl/privkey.pem \
        -out /root/captain-taxi/ssl/fullchain.pem \
        -subj "/CN=82.29.178.157"
fi

# 3. Create uploads directory
mkdir -p /root/captain-taxi/uploads

# 4. Pull & build all containers
echo "[3] Building all agent containers..."
cd /root/captain-taxi
docker compose build --parallel

# 5. Start all services
echo "[4] Starting all services..."
docker compose up -d

# 6. Wait for DB to be ready
echo "[5] Waiting for database..."
sleep 10

# 7. Run database migrations
echo "[6] Running Alembic migrations..."
docker compose exec orchestrator alembic upgrade head || echo "  Migration skipped (may already be current)"

# 8. Health check
echo "[7] Health checks..."
sleep 5
for port in 8000 8001 8002 8003 8004 8005 8006; do
    status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "000")
    echo "  Port $port: HTTP $status"
done

echo ""
echo "========================================="
echo "  Deployment complete!"
echo "========================================="
echo ""
echo "Dashboard:   http://82.29.178.157"
echo "Logs:        docker compose logs -f"
echo "Restart all: docker compose restart"
echo ""
echo "NEXT STEPS:"
echo "  1. Add ElevenLabs API key to .env"
echo "  2. Add Twilio phone number to .env (TWILIO_PHONE_FROM)"
echo "  3. Run QuickBooks OAuth: visit http://82.29.178.157/api/accounts/qb/auth"
echo "  4. Configure Vapi phone numbers in Vapi dashboard"
echo "  5. Set Twilio webhook URL to: http://82.29.178.157/webhooks/twilio/"
echo "  6. Set Vapi webhook URL to:   http://82.29.178.157/webhooks/vapi/"
echo ""
