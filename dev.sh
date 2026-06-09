#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS=()

cleanup() {
  echo ""
  echo "⏹  Shutting down..."
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait
  echo "✅  All processes stopped."
  exit 0
}

trap cleanup SIGINT SIGTERM

# ── 0. Free ports ──────────────────────────────────────────────────────────────
for PORT in 8080 6001 3000; do
  PIDS_ON_PORT=$(lsof -ti tcp:"$PORT" 2>/dev/null || true)
  if [ -n "$PIDS_ON_PORT" ]; then
    echo "⚠️   Killing processes on port $PORT: $PIDS_ON_PORT"
    kill $PIDS_ON_PORT 2>/dev/null || true
  fi
done
sleep 1

# ── 1. Backend ─────────────────────────────────────────────────────────────────
mkdir -p "$REPO_ROOT/state"
(
  cd "$REPO_ROOT"
  AUTH_TYPE=NO_AUTH \
  SECRET_MANAGER_TYPE=FILE \
  SECRET_MANAGER_DIRECTORY=./state \
  DATABASE_CONNECTION_STRING="sqlite:////$(pwd)/state/db.sqlite3?check_same_thread=False" \
  PUSHER_APP_ID=1 PUSHER_APP_KEY=keepappkey PUSHER_APP_SECRET=keepappsecret \
  PUSHER_HOST=localhost PUSHER_PORT=6001 PORT=8080 \
    poetry run uvicorn keep.api.api:get_app --factory --reload --reload-dir keep --port 8080
) &
PIDS+=($!)
echo "🐍  Backend started (PID ${PIDS[-1]})"

# ── 2. WebSocket server (Soketi) ────────────────────────────────────────────────
docker run --rm \
  -p 6001:6001 \
  -p 9601:9601 \
  -e SOKETI_DEFAULT_APP_ID=1 \
  -e SOKETI_DEFAULT_APP_KEY=keepappkey \
  -e SOKETI_DEFAULT_APP_SECRET=keepappsecret \
  -e SOKETI_DEBUG=1 \
  quay.io/soketi/soketi:1.4-16-debian &
PIDS+=($!)
echo "🔌  WebSocket server started (PID ${PIDS[-1]})"

# ── 3. Frontend ────────────────────────────────────────────────────────────────
(
  cd "$REPO_ROOT/keep-ui"
  npm run dev
) &
PIDS+=($!)
echo "🌐  Frontend started (PID ${PIDS[-1]})"

echo ""
echo "All services running. Press Ctrl+C to stop."
echo "  Backend   → http://localhost:8080"
echo "  WebSocket → ws://localhost:6001"
echo "  Frontend  → http://localhost:3000"
echo ""

wait

# Build Backend
# docker build --platform linux/amd64 -f docker/Dockerfile.api -t europe-west3-docker.pkg.dev/hoprassociation/docker-images/keep-api:latest .
# docker push europe-west3-docker.pkg.dev/hoprassociation/docker-images/keep-api:latest

# Build Frontend
# cd /Users/ausias/Documents/github/open-source/keep/keep-ui && npm install 2>&1
# docker build --platform linux/amd64 -f docker/Dockerfile.ui -t europe-west3-docker.pkg.dev/hoprassociation/docker-images/keep-ui:latest ./keep-ui/
# docker push europe-west3-docker.pkg.dev/hoprassociation/docker-images/keep-ui:latest
