#!/usr/bin/env bash

set -Eeuo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"
MCP_PROTOCOL_VERSION="${MCP_PROTOCOL_VERSION:-2026-07-28}"

if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl is required" >&2
    exit 1
fi

if [[ -z "${MCP_API_TOKEN:-}" ]]; then
    echo "ERROR: MCP_API_TOKEN must be present in the process environment" >&2
    exit 1
fi

response_file="$(mktemp)"
cleanup() {
    rm -f -- "$response_file"
}
trap cleanup EXIT

health_body="$(curl --silent --show-error --fail \
    --connect-timeout 5 --max-time 10 \
    "$BASE_URL/healthz")"
if [[ "$health_body" != '{"status":"ok"}' ]]; then
    echo "ERROR: unexpected /healthz response" >&2
    exit 1
fi
echo "PASS: /healthz"

tbox_status="$(curl --silent --show-error \
    --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 10 \
    --header 'Content-Type: application/json' \
    --request POST --data '{}' \
    "$BASE_URL/api/tbox/chat")"
if [[ "$tbox_status" != "422" ]]; then
    echo "ERROR: /api/tbox/chat route check returned HTTP $tbox_status" >&2
    exit 1
fi
echo "PASS: /api/tbox/chat is routed (validation returned 422)"

unauthorized_status="$(curl --silent --show-error \
    --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 10 \
    --header 'Content-Type: application/json' \
    --header 'Accept: application/json, text/event-stream' \
    --request POST --data '{}' \
    "$BASE_URL/mcp")"
if [[ "$unauthorized_status" != "401" ]]; then
    echo "ERROR: unauthenticated /mcp check returned HTTP $unauthorized_status" >&2
    exit 1
fi
echo "PASS: /mcp rejects missing Bearer token"

initialize_payload="$(printf \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"%s","capabilities":{},"clientInfo":{"name":"careerpulse-deploy-smoke","version":"1.0.0"}}}' \
    "$MCP_PROTOCOL_VERSION")"

authenticated_status="$(curl --silent --show-error \
    --output "$response_file" --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 30 \
    --header "Authorization: Bearer $MCP_API_TOKEN" \
    --header 'Content-Type: application/json' \
    --header 'Accept: application/json, text/event-stream' \
    --request POST --data "$initialize_payload" \
    "$BASE_URL/mcp")"
if [[ "$authenticated_status" != "200" ]] || ! grep -q '"result"' "$response_file"; then
    echo "ERROR: authenticated MCP initialize failed with HTTP $authenticated_status" >&2
    exit 1
fi
echo "PASS: authenticated MCP initialize"

echo "CareerPulse deployment smoke test passed for $BASE_URL"
