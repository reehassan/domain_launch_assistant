#!/usr/bin/env bash
# Self-contained end-to-end test. No jq required — uses python3 (already
# in your venv) to pull fields out of each JSON response.
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
echo "== 3. Generate brand ideas =="
GENERATE_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/generate-brands/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"count": 5}')
echo "$GENERATE_RESPONSE"

echo
echo "== 4. List brand ideas =="
BRANDS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/brands/" \
  -H "Authorization: Bearer $TOKEN")
echo "$BRANDS_RESPONSE"

BRAND_ID=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    # NOTE: brands/ currently returns a bare list, not {'results': [...]}
    # like api-contract.md section 13 says and unlike domains/launches
    # list endpoints. Handling both shapes here so the test can keep
    # running — but this inconsistency is worth fixing at the source.
    items = data if isinstance(data, list) else data.get('results', [])
    print(items[0]['id'])
except Exception:
    print('')
" "$BRANDS_RESPONSE")

if [ -z "$BRAND_ID" ]; then
  echo "!! No brands returned, stopping. (If generate-brands is async in your build, add a 'sleep 3' before step 4.)"
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
echo "== 6. Start domain search =="
DOMAIN_SEARCH_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/domain-search/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_idea_id\": \"$BRAND_ID\", \"extensions\": [\".com\", \".ai\", \".io\"]}")
echo "$DOMAIN_SEARCH_RESPONSE"

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
echo "== 9. Run domain checks (DNS_RESOLUTION + DOMAIN_READINESS) =="
CHECK_RESPONSE=$(curl -s -X POST "$BASE_URL/domains/$DOMAIN_ID/check/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"check_types": ["DNS_RESOLUTION", "DOMAIN_READINESS"]}')
echo "$CHECK_RESPONSE"

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