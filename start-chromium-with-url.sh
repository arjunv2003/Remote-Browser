#!/usr/bin/env bash
set -eu

CHROMIUM_BIN="/usr/bin/chromium"
PROFILE_DIR="/tmp/chromium-profile"

if [ -x /usr/lib/chromium/chrome-wrapper ]; then
  CHROMIUM_BIN="/usr/lib/chromium/chrome-wrapper"
fi

rm -rf "${PROFILE_DIR}"
mkdir -p "${PROFILE_DIR}"

if [ -n "${START_URL:-}" ]; then
  exec "${CHROMIUM_BIN}" \
    --window-position=0,0 \
    --display="${DISPLAY}" \
    --user-data-dir="${PROFILE_DIR}" \
    --no-first-run \
    --no-default-browser-check \
    --start-maximized \
    --bwsi \
    --force-dark-mode \
    --disable-extensions \
    --disable-file-system \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-dev-shm-usage \
    --disable-session-crashed-bubble \
    --new-window \
    "${START_URL}"
fi

exec "${CHROMIUM_BIN}" \
  --window-position=0,0 \
  --display="${DISPLAY}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  --start-maximized \
  --bwsi \
  --force-dark-mode \
  --disable-extensions \
  --disable-file-system \
  --disable-gpu \
  --disable-software-rasterizer \
  --disable-dev-shm-usage \
  --disable-session-crashed-bubble
