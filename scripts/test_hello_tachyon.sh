#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
APP_NAME="hello_tachyon"
USER_ID="test"
SESSION_ID="s$RANDOM"

if ! command -v jq >/dev/null 2>&1; then
  echo "[WARN] jq not found; install jq for better output (https://stedolan.github.io/jq/)" >&2
fi

echo "[1/3] Creating session $SESSION_ID..."
curl -s -X POST "$API_BASE_URL/apps/$APP_NAME/users/$USER_ID/sessions/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{}' | jq . || true

echo "[2/3] Calling /run with simple text..."
RESP=$(curl -s -X POST "$API_BASE_URL/run" \
  -H "Content-Type: application/json" \
  -d '{
    "app_name":"'
