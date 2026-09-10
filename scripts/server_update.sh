#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/union_proyectos}"
REPO_URL="${REPO_URL:-https://github.com/jaguz794/union_proyectos.git}"
BRANCH="${BRANCH:-main}"
PORTAL_HTTP_PORT="${PORTAL_HTTP_PORT:-9000}"
PORTAL_BIND_ADDRESS="${PORTAL_BIND_ADDRESS:-127.0.0.1}"

mkdir -p "$(dirname "$APP_DIR")"

if ! command -v git >/dev/null 2>&1; then
  echo "git no esta instalado."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker no esta instalado."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose no esta disponible."
  exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

if ! git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
  git checkout -B "$BRANCH" "origin/$BRANCH"
else
  git checkout "$BRANCH"
fi

before="$(git rev-parse HEAD 2>/dev/null || true)"
git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"
after="$(git rev-parse HEAD 2>/dev/null || true)"

if [ "$before" != "$after" ]; then
  echo "Actualizado: $before -> $after"
else
  echo "Sin cambios nuevos."
fi

PORTAL_BIND_ADDRESS="$PORTAL_BIND_ADDRESS" PORTAL_HTTP_PORT="$PORTAL_HTTP_PORT" docker compose up -d --build
