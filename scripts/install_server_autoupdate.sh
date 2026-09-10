#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/union_proyectos}"
REPO_URL="${REPO_URL:-https://github.com/jaguz794/union_proyectos.git}"
BRANCH="${BRANCH:-main}"
PORTAL_HTTP_PORT="${PORTAL_HTTP_PORT:-9000}"
PORTAL_BIND_ADDRESS="${PORTAL_BIND_ADDRESS:-127.0.0.1}"
CONFIGURE_APACHE_PROXY="${CONFIGURE_APACHE_PROXY:-1}"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=()
else
  if ! command -v sudo >/dev/null 2>&1; then
    echo "Ejecuta este instalador como root o instala sudo primero."
    exit 1
  fi
  SUDO=(sudo)
fi

if command -v apt-get >/dev/null 2>&1; then
  "${SUDO[@]}" apt-get update
  "${SUDO[@]}" apt-get install -y git ca-certificates curl
  if ! command -v docker >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get install -y docker.io
  fi
  if ! docker compose version >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get install -y docker-compose-plugin || "${SUDO[@]}" apt-get install -y docker-compose
  fi
  if [ "$CONFIGURE_APACHE_PROXY" = "1" ] && ! command -v apache2ctl >/dev/null 2>&1; then
    "${SUDO[@]}" apt-get install -y apache2
  fi
fi

"${SUDO[@]}" systemctl enable --now docker

"${SUDO[@]}" mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d "$APP_DIR/.git" ]; then
  "${SUDO[@]}" git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

"${SUDO[@]}" tee /etc/systemd/system/union-proyectos-update.service >/dev/null <<SERVICE
[Unit]
Description=Actualizar y levantar Portal Union Proyectos
Wants=network-online.target docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
Environment=APP_DIR=$APP_DIR
Environment=REPO_URL=$REPO_URL
Environment=BRANCH=$BRANCH
Environment=PORTAL_HTTP_PORT=$PORTAL_HTTP_PORT
Environment=PORTAL_BIND_ADDRESS=$PORTAL_BIND_ADDRESS
ExecStart=/bin/bash $APP_DIR/scripts/server_update.sh
SERVICE

"${SUDO[@]}" tee /etc/systemd/system/union-proyectos-update.timer >/dev/null <<TIMER
[Unit]
Description=Buscar cambios del Portal Union Proyectos cada minuto

[Timer]
OnBootSec=30
OnUnitActiveSec=60
AccuracySec=10
Persistent=true
Unit=union-proyectos-update.service

[Install]
WantedBy=timers.target
TIMER

"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now union-proyectos-update.timer
"${SUDO[@]}" systemctl start union-proyectos-update.service

if [ "$CONFIGURE_APACHE_PROXY" = "1" ] && command -v apache2ctl >/dev/null 2>&1; then
  "${SUDO[@]}" a2enmod proxy proxy_http headers >/dev/null
  "${SUDO[@]}" tee /etc/apache2/sites-available/union-proyectos.conf >/dev/null <<APACHE
<VirtualHost *:80>
    ServerName 192.168.10.7
    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:$PORTAL_HTTP_PORT/
    ProxyPassReverse / http://127.0.0.1:$PORTAL_HTTP_PORT/
    ErrorLog \${APACHE_LOG_DIR}/union_proyectos_error.log
    CustomLog \${APACHE_LOG_DIR}/union_proyectos_access.log combined
</VirtualHost>
APACHE
  "${SUDO[@]}" a2ensite union-proyectos.conf >/dev/null
  "${SUDO[@]}" systemctl reload apache2
fi

"${SUDO[@]}" systemctl status union-proyectos-update.service --no-pager
