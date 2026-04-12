#!/usr/bin/env bash
# =============================================================================
# Captain Taxi — Customer Service Agent
# VPS install script (Ubuntu 22.04 / Debian 12)
#
# Run as root on a fresh Hostinger VPS:
#   bash install.sh
# =============================================================================
set -euo pipefail

APP_DIR="/opt/captain-taxi"
APP_USER="captaintaxi"
LOG_DIR="/var/log/captain-taxi"
PYTHON="python3.11"

echo "=== Captain Taxi Customer Service Agent — Install ==="

# ── System packages ───────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib \
    redis-server \
    nginx \
    certbot python3-certbot-nginx \
    git build-essential libpq-dev

# ── App user ──────────────────────────────────────────────────────────────────
id -u "$APP_USER" &>/dev/null || useradd -r -s /bin/false -d "$APP_DIR" "$APP_USER"

# ── Directories ───────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR" "$LOG_DIR"
chown "$APP_USER:$APP_USER" "$APP_DIR" "$LOG_DIR"

# ── Python virtualenv ─────────────────────────────────────────────────────────
if [ ! -d "$APP_DIR/venv" ]; then
    echo "Creating virtualenv…"
    $PYTHON -m venv "$APP_DIR/venv"
fi

# ── Install dependencies ──────────────────────────────────────────────────────
echo "Installing Python dependencies…"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/customer/requirements.txt"

# ── PostgreSQL ────────────────────────────────────────────────────────────────
echo "Configuring PostgreSQL…"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='captaintaxi'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER captaintaxi WITH PASSWORD 'CHANGE_ME_IN_PRODUCTION';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='captaintaxi'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE captaintaxi OWNER captaintaxi;"

# ── Redis ─────────────────────────────────────────────────────────────────────
systemctl enable redis-server --now

# ── Systemd service ───────────────────────────────────────────────────────────
echo "Installing systemd service…"
cp "$APP_DIR/customer/deploy/captain-taxi-customer.service" \
    /etc/systemd/system/captain-taxi-customer.service
systemctl daemon-reload
systemctl enable captain-taxi-customer

# ── Nginx ─────────────────────────────────────────────────────────────────────
echo "Configuring nginx…"
cp "$APP_DIR/customer/deploy/nginx.conf" \
    /etc/nginx/sites-available/customer.captaintaxi.ca
ln -sf /etc/nginx/sites-available/customer.captaintaxi.ca \
       /etc/nginx/sites-enabled/customer.captaintaxi.ca
nginx -t && systemctl reload nginx

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to $APP_DIR/.env and fill in all values"
echo "  2. Run: certbot --nginx -d customer.captaintaxi.ca"
echo "  3. Run: systemctl start captain-taxi-customer"
echo "  4. Run: $APP_DIR/venv/bin/python -m captain_taxi.customer.vapi.setup"
echo "  5. Configure Twilio SMS webhook: https://customer.captaintaxi.ca/webhook/twilio/sms"
echo "  6. Configure Twilio WhatsApp webhook: https://customer.captaintaxi.ca/webhook/twilio/whatsapp"
echo ""
