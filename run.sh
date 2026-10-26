#!/usr/bin/env bash
# ECO-GALLO UAA · arranca backend (Python/Flask) + gateway (Java)
set -e
cd "$(dirname "$0")"
export ECOGALLO_SEED="${ECOGALLO_SEED:-1}"
# Sin SMTP configurado, el código también se muestra en pantalla (SOLO desarrollo).
if [ -z "$ECOGALLO_SMTP_HOST" ]; then export ECOGALLO_DEV="${ECOGALLO_DEV:-1}"; fi
PORT="${PORT:-8080}"; BPORT="${ECOGALLO_BACKEND_PORT:-5000}"

python3 -m pip install -q --disable-pip-version-check -r backend/requirements.txt 2>/dev/null || \
python3 -m pip install -q --break-system-packages -r backend/requirements.txt

mkdir -p gateway/out && javac -d gateway/out gateway/Gateway.java
python3 backend/app.py & BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM
sleep 1.5
echo "  Abre http://localhost:$PORT"
java -cp gateway/out Gateway "$PORT" "$BPORT" frontend
