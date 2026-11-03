#!/bin/sh
set -eu
cd "${FINN_ROOT:-/app}"
MONITOR_PID=
if [ "${FINN_MONITOR:-1}" = "1" ]; then
  "${FINN_PYTHON:-/app/venv/bin/python}" -u monitor.py --interval "${FINN_REFRESH_INTERVAL:-900}" &
  MONITOR_PID=$!
fi
cd finn-app
node node_modules/next/dist/bin/next start -p "${PORT:-3000}" &
APP_PID=$!
trap 'kill $MONITOR_PID "$APP_PID" 2>/dev/null || true' EXIT INT TERM
wait "$APP_PID"
