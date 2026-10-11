#!/usr/bin/env bash
# Post-deploy smoke test: waits for /health, then does a create -> read -> delete round trip.
# Usage: ./scripts/smoke_test.sh http://localhost:5000
set -euo pipefail
BASE="${1:-http://localhost:5000}"

echo "Waiting for $BASE/health ..."
for i in $(seq 1 30); do
  if curl -fsS "$BASE/health" >/dev/null 2>&1; then echo "healthy after ${i} attempt(s)"; break; fi
  [ "$i" -eq 30 ] && { echo "FAILED: app never became healthy"; exit 1; }
  sleep 2
done

EMAIL="smoke-$(date +%s)@example.com"
RESP=$(curl -fsS -X POST "$BASE/api/students" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke Test\",\"email\":\"$EMAIL\",\"course\":\"QA\",\"year\":1}")
ID=$(echo "$RESP" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "created student id=$ID"

curl -fsS "$BASE/api/students/$ID" | grep -q "$EMAIL" && echo "read back OK"
curl -fsS "$BASE/metrics" | grep -q '^sms_students_total' && echo "metrics OK"
curl -fsS -X DELETE "$BASE/api/students/$ID" -o /dev/null && echo "cleanup OK"

echo "SMOKE TEST PASSED"
