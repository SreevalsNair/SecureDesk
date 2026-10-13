#!/usr/bin/env bash
# deploy/setup.sh
# Idempotent server setup for SecureDesk on Ubuntu 22.04 ARM64 (AWS t4g)
# Run as: sudo bash deploy/setup.sh
# Re-running this script is safe — it skips steps that are already done.

set -euo pipefail

APP_DIR="/var/www/securedesk"
APP_USER="securedesk"
PYTHON="python3"
SERVICE="securedesk"

echo "=== SecureDesk Setup ==="

# ── 1. Swap file (helps on 1 GB RAM instance during pip install) ────────────
if [ ! -f /swapfile ]; then
    echo "-- Creating 1 GB swap file..."
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "   Swap created."
else
    echo "-- Swap file already exists. Skipping."
fi

# ── 2. System packages ────────────────────────────────────────────────────────
echo "-- Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx git

# ── 3. Create non-root app user ────────────────────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
    echo "   User '$APP_USER' created."
else
    echo "-- User '$APP_USER' already exists. Skipping."
fi

# ── 4. App directory ──────────────────────────────────────────────────────────
mkdir -p "$APP_DIR/logs"
if [ ! -d "$APP_DIR/app" ]; then
    echo "-- Copying application files..."
    cp -r . "$APP_DIR/"
fi

# ── 5. Virtual environment ─────────────────────────────────────────────────────
if [ ! -d "$APP_DIR/venv" ]; then
    echo "-- Creating Python virtual environment..."
    $PYTHON -m venv "$APP_DIR/venv"
fi
echo "-- Installing Python dependencies..."
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── 6. .env file ──────────────────────────────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "-- Creating .env from example..."
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    # Generate a random SECRET_KEY
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|REPLACE_WITH_A_STRONG_RANDOM_SECRET|$SECRET|" "$APP_DIR/.env"
    echo "   !!! Edit $APP_DIR/.env to set ADMIN_EMAIL and ADMIN_PASSWORD before starting."
fi

# ── 7. Initialise database ─────────────────────────────────────────────────────
echo "-- Initialising database..."
cd "$APP_DIR"
"$APP_DIR/venv/bin/python" manage.py init-db

# ── 8. File permissions ────────────────────────────────────────────────────────
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 750 "$APP_DIR"
chmod 640 "$APP_DIR/.env"

# ── 9. Nginx configuration ─────────────────────────────────────────────────────
echo "-- Configuring Nginx..."
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/securedesk
ln -sf /etc/nginx/sites-available/securedesk /etc/nginx/sites-enabled/securedesk
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
echo "   Nginx configured."

# ── 10. Systemd service ────────────────────────────────────────────────────────
echo "-- Installing systemd service..."
cp "$APP_DIR/deploy/securedesk.service" /etc/systemd/system/securedesk.service
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
echo "   Service started."

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit $APP_DIR/.env (set ADMIN_EMAIL, ADMIN_PASSWORD, SESSION_COOKIE_SECURE)"
echo "  2. Run: sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/manage.py create-admin"
echo "  3. Open port 80 in your EC2 Security Group"
echo "  4. (Optional) Set up HTTPS: sudo apt install certbot python3-certbot-nginx && sudo certbot --nginx"
echo "  5. Check logs: sudo journalctl -u securedesk -f"
