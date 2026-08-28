#!/usr/bin/env bash
# Negative-path test for DomainClaimsService: proves a name.com timeout
# never gets persisted as "no claims" (Day 2, Feature 4 checklist item).
#
# THIS SCRIPT DOES NOT SWAP ENV VARS FOR YOU — Django reads
# NAMECOM_BASE_URL once at process startup via decouple's config(), so
# there's no way to fake a timeout mid-request from bash. You must:
#
#   1. In your .env, temporarily set:
#        NAMECOM_BASE_URL=http://10.255.255.1/core/v1
#      (10.255.255.1 is a non-routable address — any request to it will
#      hang until NameComClient's 10s timeout fires, giving you a real
#      requests.Timeout without touching any Python code.)
#   2. Restart BOTH the Django dev server and the Celery worker (both
#      read settings at import time).
#   3. Run: bash scripts/test_claims_fault.sh <PROJECT_ID> <DOMAIN_ID>
#      (use the ids printed at the end of test_flow.sh's last run)
#   4. Revert NAMECOM_BASE_URL in .env and restart both processes again
#      before doing anything else — while it's pointed at 10.255.255.1,
#      EVERY name.com call (availability checks included) will hang.
#
# Usage: bash test_claims_fault.sh <PROJECT_ID> <DOMAIN_ID>

set -u

BASE_URL="http://127.0.0.1:8000/api/v1"
USERNAME="areebahassan"
PASSWORD="qazqaz786"

PROJECT_ID="${1:?Usage: bash test_claims_fault.sh <PROJECT_ID> <DOMAIN_ID>}"
DOMAIN_ID="${2:?Usage: bash test_claims_fault.sh <PROJECT_ID> <DOMAIN_ID>}"

extract() {
  python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(data.get(sys.argv[2], '') or '')
except Exception:
    print('')
" "$1" "$2"
}

poll_task() {
  local task_id="$1"
  local elapsed=0
  local interval=2
  local timeout=30

  while [ "$elapsed" -lt "$timeout" ]; do
    local resp
    resp=$(curl -s -X GET "$BASE_URL/tasks/$task_id/" \
      -H "Authorization: Bearer $TOKEN")
    local task_status
    task_status=$(extract "$resp" "status")

    if [ "$task_status" = "SUCCESS" ] || [ "$task_status" = "FAILURE" ]; then
      echo "$resp"
      return 0
    fi

    sleep "$interval"
    elapsed=$((elapsed + interval))
  done

  echo "!! Task $task_id did not finish within ${timeout}s (last status: $task_status)" >&2
  return 1
}

echo "== 1. Login =="
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$USERNAME\", \"password\": \"$PASSWORD\"}")

TOKEN=$(extract "$LOGIN_RESPONSE" "access")
if [ -z "$TOKEN" ]; then
  echo "!! Login failed, stopping."
  exit 1
fi
echo "-> TOKEN acquired"

echo
echo "== 2. Baseline: count existing claims for this domain BEFORE the fault run =="
BEFORE_RESPONSE=$(curl -s -X GET "$BASE_URL/domains/$DOMAIN_ID/claims/" \
  -H "Authorization: Bearer $TOKEN")
echo "$BEFORE_RESPONSE"

BEFORE_COUNT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(len(data.get('results', [])))
except Exception:
    print(-1)
" "$BEFORE_RESPONSE")
echo "-> BEFORE_COUNT=$BEFORE_COUNT"

if [ "$BEFORE_COUNT" = "-1" ]; then
  echo "!! Could not read claims list, stopping."
  exit 1
fi

echo
echo "== 3. Dispatch check-claims/ — this call should hit the unreachable"
echo "   NAMECOM_BASE_URL you configured and time out after ~10s inside"
echo "   the Celery worker. =="
CLAIMS_RESPONSE=$(curl -s -X POST "$BASE_URL/domains/$DOMAIN_ID/check-claims/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN")
echo "$CLAIMS_RESPONSE"

CLAIMS_TASK_ID=$(extract "$CLAIMS_RESPONSE" "task_id")
if [ -z "$CLAIMS_TASK_ID" ]; then
  echo "!! No task_id returned, stopping."
  exit 1
fi
echo "-> CLAIMS_TASK_ID=$CLAIMS_TASK_ID"

echo
echo "== 4. Poll — expect FAILURE, error.code=EXTERNAL_API_TIMEOUT =="
CLAIMS_TASK_RESULT=$(poll_task "$CLAIMS_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Task never resolved within 30s. If NAMECOM_BASE_URL is set to"
  echo "   10.255.255.1, the task itself should still fail around the"
  echo "   10s NameComClient timeout — a 30s poll timeout on TOP of that"
  echo "   would suggest something else is wrong (worker not restarted?)."
  exit 1
fi
echo "$CLAIMS_TASK_RESULT"

CLAIMS_TASK_STATUS=$(extract "$CLAIMS_TASK_RESULT" "status")
ERROR_CODE=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    err = data.get('error') or {}
    print(err.get('code', ''))
except Exception:
    print('')
" "$CLAIMS_TASK_RESULT")

echo "-> task.status=$CLAIMS_TASK_STATUS  error.code=$ERROR_CODE"

if [ "$CLAIMS_TASK_STATUS" = "SUCCESS" ]; then
  echo "!!!! BUG: task SUCCEEDED against an unreachable host. This must not"
  echo "!!!! happen — investigate DomainClaimsService/NameComClient immediately."
elif [ "$ERROR_CODE" != "EXTERNAL_API_TIMEOUT" ]; then
  echo "!! Task failed, but with error.code=$ERROR_CODE instead of the"
  echo "   expected EXTERNAL_API_TIMEOUT. Worth double-checking which"
  echo "   exception NameComClient actually raised."
else
  echo "-> Correct: failed cleanly with EXTERNAL_API_TIMEOUT."
fi

echo
echo "== 5. Re-check claims list AFTER the fault run — count must be UNCHANGED =="
AFTER_RESPONSE=$(curl -s -X GET "$BASE_URL/domains/$DOMAIN_ID/claims/" \
  -H "Authorization: Bearer $TOKEN")
echo "$AFTER_RESPONSE"

AFTER_COUNT=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(len(data.get('results', [])))
except Exception:
    print(-1)
" "$AFTER_RESPONSE")
echo "-> AFTER_COUNT=$AFTER_COUNT"

echo
if [ "$AFTER_COUNT" = "$BEFORE_COUNT" ]; then
  echo "== PASS: claim count unchanged ($BEFORE_COUNT -> $AFTER_COUNT)."
  echo "   The timeout was NOT persisted as a claims result. =="
else
  echo "!!!! FAIL: claim count changed ($BEFORE_COUNT -> $AFTER_COUNT) after a"
  echo "!!!! timeout. A row got written that should not exist — this is"
  echo "!!!! exactly the 'timeout misread as no claims' bug the checklist"
  echo "!!!! called out. Investigate DomainClaimsService.check_claims()."
fi

echo
echo "== Reminder: revert NAMECOM_BASE_URL in .env and restart both the"
echo "   Django server and the Celery worker before doing anything else. =="