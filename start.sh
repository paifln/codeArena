#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
docker info >/dev/null
if [ -z "${DOCKER_GID:-}" ] && [ -S /var/run/docker.sock ]; then
  DOCKER_GID=$(stat -c '%g' /var/run/docker.sock)
  export DOCKER_GID
fi
docker compose up --build -d
printf '\nCodeArena: http://localhost:%s\n' "${PORT:-8000}"
printf 'Published address (includes .env overrides):\n'
docker compose port api 8000
if command -v hostname >/dev/null 2>&1; then
  printf 'LAN addresses (choose the address of your local network):\n'
  hostname -I 2>/dev/null || true
fi
docker compose ps
