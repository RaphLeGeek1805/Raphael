#!/usr/bin/env bash
# Installation script for the Raphael Flask app on Ubuntu.
# Run as the `ubuntu` user. Uses sudo for system packages.
#
# Usage:
#   bash deploy.sh
#
# Environment variables (optional):
#   APP_DIR        Path to clone/place the app (default: /home/ubuntu/raphael)
#   REPO_URL       Git URL to clone (default: empty -> assumes APP_DIR already exists)
#   BRANCH         Git branch to checkout (default: main)
#   DOMAIN         Domain name for nginx (default: _ -> any host)
#   PORT           Internal gunicorn port (default: 8000)
#   SECRET_KEY     Flask secret key (default: random)
#   SERPAPI_KEY    Optional SerpAPI key
#   GITHUB_TOKEN   Optional GitHub token

set -euo pipefail

APP_DIR="${APP_DIR:-/home/ubuntu/raphael}"
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
DOMAIN="${DOMAIN:-_}"
PORT="${PORT:-8000}"
SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | base64)}"
SERPAPI_KEY="${SERPAPI_KEY:-}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"

SERVICE_USER="ubuntu"
SERVICE_NAME="raphael"

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }

log "1/7 Updating apt and installing system packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-venv python3-pip \
    git nginx \
    libjpeg-dev zlib1g-dev libpng-dev \
    build-essential

log "2/7 Preparing application directory at ${APP_DIR}"
if [ -n "${REPO_URL}" ]; then
    if [ ! -d "${APP_DIR}/.git" ]; then
        sudo -u "${SERVICE_USER}" git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
    else
        sudo -u "${SERVICE_USER}" git -C "${APP_DIR}" fetch origin
        sudo -u "${SERVICE_USER}" git -C "${APP_DIR}" checkout "${BRANCH}"
        sudo -u "${SERVICE_USER}" git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
    fi
else
    if [ ! -d "${APP_DIR}" ]; then
        echo "ERROR: ${APP_DIR} does not exist and REPO_URL is empty." >&2
        echo "Either set REPO_URL=... or upload the source to ${APP_DIR} first." >&2
        exit 1
    fi
fi
sudo chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}"

log "3/7 Creating Python virtualenv and installing dependencies"
sudo -u "${SERVICE_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"
sudo -u "${SERVICE_USER}" "${APP_DIR}/.venv/bin/pip" install gunicorn

log "4/7 Writing environment file"
ENV_FILE="${APP_DIR}/.env"
sudo -u "${SERVICE_USER}" tee "${ENV_FILE}" >/dev/null <<EOF
SECRET_KEY=${SECRET_KEY}
SERPAPI_KEY=${SERPAPI_KEY}
GITHUB_TOKEN=${GITHUB_TOKEN}
EOF
sudo chmod 600 "${ENV_FILE}"
sudo chown "${SERVICE_USER}:${SERVICE_USER}" "${ENV_FILE}"

log "5/7 Installing systemd service"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF
[Unit]
Description=Raphael Flask app (gunicorn)
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/.venv/bin/gunicorn \\
    --workers 3 \\
    --bind 127.0.0.1:${PORT} \\
    --access-logfile - \\
    --error-logfile - \\
    app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

log "6/7 Configuring nginx reverse proxy"
sudo tee "/etc/nginx/sites-available/${SERVICE_NAME}" >/dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 12M;

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

sudo ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

log "7/7 Done"
echo
echo "Service status:"
sudo systemctl --no-pager --full status "${SERVICE_NAME}" | head -n 15 || true
echo
echo "App should be reachable on http://${DOMAIN}/ (or http://<server-ip>/ if DOMAIN=_)"
echo "Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
echo "Restart: sudo systemctl restart ${SERVICE_NAME}"
