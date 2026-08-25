#!/usr/bin/env bash
# Self-contained end-to-end test. No jq required — uses python3 (already
# in your venv) to pull fields out of each JSON response.
#
# Day 6 update: generate-brands/, domain-search/, and check/ are all
# async now (202 + task_id). Each of those steps polls
# GET /tasks/{task_id}/ until SUCCESS/FAILURE instead of assuming the
# result is ready in the same response.
#
# Usage: bash test_flow.sh

BASE_URL="http://127.0.0.1:8000/api/v1"
USERNAME="areebahassan"
PASSWORD="qazqaz786"

extract() {
  # extract <json> <key> — pulls a top-level key with python3, prints
  # nothing (empty string) if missing rather than crashing the script.
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
  # poll_task <task_id> — polls GET /tasks/{id}/ every 2s, up to 30s.
  # Prints the final task JSON to stdout on SUCCESS or FAILURE, prints
  # nothing and returns 1 on timeout.
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
echo "$LOGIN_RESPONSE"

TOKEN=$(extract "$LOGIN_RESPONSE" "access")
if [ -z "$TOKEN" ]; then
  echo "!! Login failed, stopping. Check server is running and credentials are correct."
  exit 1
fi
echo "-> TOKEN acquired"

echo
echo "== 2. Create project =="
PROJECT_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "LedgerFlow", "business_description": "An AI-powered bookkeeping platform for small businesses."}')
echo "$PROJECT_RESPONSE"

PROJECT_ID=$(extract "$PROJECT_RESPONSE" "id")
if [ -z "$PROJECT_ID" ]; then
  echo "!! Project creation failed, stopping."
  exit 1
fi
echo "-> PROJECT_ID=$PROJECT_ID"

echo
echo "== 3. Generate brand ideas (async — dispatch) =="
GENERATE_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/generate-brands/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"count": 5}')
echo "$GENERATE_RESPONSE"

GENERATE_TASK_ID=$(extract "$GENERATE_RESPONSE" "task_id")
if [ -z "$GENERATE_TASK_ID" ]; then
  echo "!! No task_id returned from generate-brands, stopping."
  exit 1
fi
echo "-> GENERATE_TASK_ID=$GENERATE_TASK_ID"

echo
echo "== 3b. Poll brand generation task =="
GENERATE_TASK_RESULT=$(poll_task "$GENERATE_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Brand generation task did not complete, stopping."
  exit 1
fi
echo "$GENERATE_TASK_RESULT"

GENERATE_TASK_STATUS=$(extract "$GENERATE_TASK_RESULT" "status")
if [ "$GENERATE_TASK_STATUS" != "SUCCESS" ]; then
  echo "!! Brand generation task FAILED, stopping."
  exit 1
fi

echo
echo "== 4. List brand ideas =="
BRANDS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/brands/" \
  -H "Authorization: Bearer $TOKEN")
echo "$BRANDS_RESPONSE"

BRAND_ID=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    items = data if isinstance(data, list) else data.get('results', [])
    print(items[0]['id'])
except Exception:
    print('')
" "$BRANDS_RESPONSE")

if [ -z "$BRAND_ID" ]; then
  echo "!! No brands returned, stopping."
  exit 1
fi
echo "-> BRAND_ID=$BRAND_ID"

echo
echo "== 5. Select brand =="
SELECT_BRAND_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/select-brand/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_id\": \"$BRAND_ID\"}")
echo "$SELECT_BRAND_RESPONSE"

echo
echo "== 6. Start domain search (async — dispatch) =="
DOMAIN_SEARCH_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/domain-search/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_idea_id\": \"$BRAND_ID\", \"extensions\": [\".com\", \".ai\", \".io\"]}")
echo "$DOMAIN_SEARCH_RESPONSE"

SEARCH_TASK_ID=$(extract "$DOMAIN_SEARCH_RESPONSE" "task_id")
if [ -z "$SEARCH_TASK_ID" ]; then
  echo "!! No task_id returned from domain-search, stopping."
  exit 1
fi
echo "-> SEARCH_TASK_ID=$SEARCH_TASK_ID"

echo
echo "== 6b. Poll domain search task =="
SEARCH_TASK_RESULT=$(poll_task "$SEARCH_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Domain search task did not complete, stopping."
  exit 1
fi
echo "$SEARCH_TASK_RESULT"

SEARCH_TASK_STATUS=$(extract "$SEARCH_TASK_RESULT" "status")
if [ "$SEARCH_TASK_STATUS" != "SUCCESS" ]; then
  echo "!! Domain search task FAILED, stopping."
  exit 1
fi

echo
echo "== 7. Get domain results (available=true) =="
DOMAINS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/domains/?available=true" \
  -H "Authorization: Bearer $TOKEN")
echo "$DOMAINS_RESPONSE"

DOMAIN_ID=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    print(data['results'][0]['id'])
except Exception:
    print('')
" "$DOMAINS_RESPONSE")

if [ -z "$DOMAIN_ID" ]; then
  echo "!! No available domains returned, stopping."
  exit 1
fi
echo "-> DOMAIN_ID=$DOMAIN_ID"

echo
echo "== 8. Select domain =="
SELECT_DOMAIN_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/select-domain/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"domain_id\": \"$DOMAIN_ID\"}")
echo "$SELECT_DOMAIN_RESPONSE"

echo
echo "== 9. Run domain checks (async — dispatch) =="
CHECK_RESPONSE=$(curl -s -X POST "$BASE_URL/domains/$DOMAIN_ID/check/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]}')
echo "$CHECK_RESPONSE"

CHECK_TASK_ID=$(extract "$CHECK_RESPONSE" "task_id")
if [ -z "$CHECK_TASK_ID" ]; then
  echo "!! No task_id returned from check/, stopping."
  exit 1
fi
echo "-> CHECK_TASK_ID=$CHECK_TASK_ID"

echo
echo "== 9b. Poll domain check task =="
CHECK_TASK_RESULT=$(poll_task "$CHECK_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Domain check task did not complete, stopping."
  exit 1
fi
echo "$CHECK_TASK_RESULT"

echo
echo "== 10. Get domain checks =="
CHECKS_RESPONSE=$(curl -s -X GET "$BASE_URL/domains/$DOMAIN_ID/checks/" \
  -H "Authorization: Bearer $TOKEN")
echo "$CHECKS_RESPONSE"

echo
echo "== 11. Get launch report =="
LAUNCH_REPORT_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/launch-report/" \
  -H "Authorization: Bearer $TOKEN")
echo "$LAUNCH_REPORT_RESPONSE"

echo
echo "== Done =="
echo "PROJECT_ID=$PROJECT_ID"
echo "BRAND_ID=$BRAND_ID"
echo "DOMAIN_ID=$DOMAIN_ID"
