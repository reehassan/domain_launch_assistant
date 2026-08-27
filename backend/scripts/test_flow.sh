#!/usr/bin/env bash
# Self-contained end-to-end test. No jq required — uses python3 (already
# in your venv) to pull fields out of each JSON response.
#
# Day 6 update: generate-brands/, domain-search/, and check/ are all
# async now (202 + task_id). Each of those steps polls
# GET /tasks/{task_id}/ until SUCCESS/FAILURE instead of assuming the
# result is ready in the same response.
#
# Day 7 update: added Regenerate checks for both brands and domains
# right after their first successful generate/search+select, to verify
# (a) the endpoint can be called a second time in the same project
# without a 500, and (b) the list-after-regenerate call returns exactly
# what the UI expects to show.
#
# Day 2 update: added AI domain recommendation (11), trademark claims
# check (12), and an ownership-check pass (14) that verifies a second
# user gets 404 — not the first user's data — when hitting the same
# domain/project ids.
#
# Day 3 update: added a project-status check after DNS checks (10b) and
# a Simulate Registration exercise (15) against Feature 5. NOTE:
# DNS_RESOLUTION performs a REAL socket.gethostbyname() call, and
# DOMAIN_ID here is always just an AVAILABLE (never actually registered
# or DNS-configured) domain — so DNS_RESOLUTION will almost always FAIL,
# which correctly keeps the project at VERIFYING_DNS rather than READY
# under the new all-checks-must-PASS rule. Step 15 detects this and
# explains it rather than treating the resulting 409 as a script bug.
#
# Usage: bash test_flow.sh

BASE_URL="http://127.0.0.1:8000/api/v1"
USERNAME="areebahassan"
PASSWORD="qazqaz786"

# Second account, used only in step 14 to prove ownership isolation.
# If it doesn't exist yet, step 14 registers it first.
OTHER_USERNAME="ownershiptestuser"
OTHER_EMAIL="ownershiptest@example.com"
OTHER_PASSWORD="qazqaz786"

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

get_with_status() {
  # get_with_status <url> <token> — GETs a URL, prints "HTTP <code>"
  # then the response body. Manual-inspection style, matching the rest
  # of this script — no automated pass/fail assertion, just makes the
  # status code visible next to the body so you can eyeball it.
  local url="$1"
  local token="$2"
  local resp
  resp=$(curl -s -w "\n%{http_code}" -X GET "$url" -H "Authorization: Bearer $token")
  local code
  code=$(echo "$resp" | tail -n1)
  local body
  body=$(echo "$resp" | sed '$d')
  echo "HTTP $code"
  echo "$body"
}

post_with_status() {
  # post_with_status <url> <token> [json_body] — same as above, for POST.
  local url="$1"
  local token="$2"
  local body_data="${3:-{}}"
  local resp
  resp=$(curl -s -w "\n%{http_code}" -X POST "$url" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $token" \
    -d "$body_data")
  local code
  code=$(echo "$resp" | tail -n1)
  local body
  body=$(echo "$resp" | sed '$d')
  echo "HTTP $code"
  echo "$body"
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
echo "== 4b. Regenerate brands (second generate-brands/ call, same project) =="
echo "   Checking: does the endpoint tolerate a second call without a 500,"
echo "   and does list-after-regenerate return all brands ever created"
echo "   (old batch not deleted) — the UI only *shows* the latest task"
echo "   result, but GET /brands/ is expected to return everything."
REGEN_BRAND_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/generate-brands/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"count": 5}')
echo "$REGEN_BRAND_RESPONSE"

REGEN_BRAND_TASK_ID=$(extract "$REGEN_BRAND_RESPONSE" "task_id")
if [ -z "$REGEN_BRAND_TASK_ID" ]; then
  echo "!! No task_id returned from regenerate call, stopping."
  exit 1
fi
echo "-> REGEN_BRAND_TASK_ID=$REGEN_BRAND_TASK_ID"

REGEN_BRAND_TASK_RESULT=$(poll_task "$REGEN_BRAND_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Regenerate brands task did not complete (timeout)."
else
  echo "$REGEN_BRAND_TASK_RESULT"
  REGEN_BRAND_TASK_STATUS=$(extract "$REGEN_BRAND_TASK_RESULT" "status")
  if [ "$REGEN_BRAND_TASK_STATUS" = "FAILURE" ]; then
    echo "!! Regenerate task FAILED — likely a name collision with the first batch"
    echo "   (unique_brand_name_per_project_ci is project-wide, not per-batch)."
    echo "   Not stopping the script for this — it's a known, tested failure mode,"
    echo "   not a crash. Continuing with the ORIGINAL BRAND_ID from step 4."
  fi
fi

echo
echo "== 4c. List brands again — count should reflect BOTH batches (old rows not deleted) =="
curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/brands/" \
  -H "Authorization: Bearer $TOKEN"

echo
echo "== 5. Select brand (using ORIGINAL BRAND_ID from step 4, regardless of regenerate outcome) =="
SELECT_BRAND_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/select-brand/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_id\": \"$BRAND_ID\"}")
echo "$SELECT_BRAND_RESPONSE"

echo
echo "== 6. Start domain search (async — dispatch) =="
echo "   Checking all 8 extensions VALID_EXTENSIONS supports (not just"
echo "   .com/.ai/.io) — a common, plausible SaaS name like the ones Gemini"
echo "   generates can easily have .com/.ai/.io all TAKEN in the real"
echo "   name.com data this hits; more TLDs means better odds step 7 finds"
echo "   at least one AVAILABLE result instead of stopping the script."
DOMAIN_SEARCH_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/domain-search/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_idea_id\": \"$BRAND_ID\", \"extensions\": [\".com\", \".ai\", \".io\", \".net\", \".org\", \".co\", \".dev\", \".app\"]}")
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
echo "== 6c. Regenerate domains (second domain-search/ call, same brand) =="
echo "   Checking: uniq_search_domain is scoped to (search, domain), and"
echo "   every call creates a new DomainSearch row, so this should ALWAYS"
echo "   succeed — no collision is possible by construction."
REGEN_DOMAIN_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/domain-search/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"brand_idea_id\": \"$BRAND_ID\", \"extensions\": [\".com\", \".ai\", \".io\", \".net\", \".org\", \".co\", \".dev\", \".app\"]}")
echo "$REGEN_DOMAIN_RESPONSE"

REGEN_SEARCH_TASK_ID=$(extract "$REGEN_DOMAIN_RESPONSE" "task_id")
if [ -z "$REGEN_SEARCH_TASK_ID" ]; then
  echo "!! No task_id returned from regenerate domain-search, stopping."
  exit 1
fi
echo "-> REGEN_SEARCH_TASK_ID=$REGEN_SEARCH_TASK_ID"

REGEN_SEARCH_TASK_RESULT=$(poll_task "$REGEN_SEARCH_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Regenerate domain search task did not complete, stopping."
  exit 1
fi
echo "$REGEN_SEARCH_TASK_RESULT"

REGEN_SEARCH_TASK_STATUS=$(extract "$REGEN_SEARCH_TASK_RESULT" "status")
if [ "$REGEN_SEARCH_TASK_STATUS" != "SUCCESS" ]; then
  echo "!! Regenerate domain search task FAILED — this would be unexpected"
  echo "   given uniq_search_domain's (search, domain) scoping. Worth flagging."
fi

echo
echo "== 6d. List ALL domain results for project — should include rows from BOTH searches =="
curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/domains/" \
  -H "Authorization: Bearer $TOKEN"

echo
echo "== 7. Get domain results (available=true) =="
echo "   NOTE: this filter is scoped to (project, available) only — not to"
echo "   a specific search — so it can surface AVAILABLE rows from EITHER"
echo "   the original search (6) or the regenerated one (6c), ordered by"
echo "   -checked_at. Don't assume DOMAIN_ID below came from the second search."
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

CHECK_TASK_STATUS=$(extract "$CHECK_TASK_RESULT" "status")
if [ "$CHECK_TASK_STATUS" != "SUCCESS" ]; then
  echo "!! Domain check task FAILED, stopping."
  exit 1
fi

echo
echo "== 10. Get domain checks =="
CHECKS_RESPONSE=$(curl -s -X GET "$BASE_URL/domains/$DOMAIN_ID/checks/" \
  -H "Authorization: Bearer $TOKEN")
echo "$CHECKS_RESPONSE"

echo
echo "== 10b. Check project status after DNS checks =="
echo "   NOTE: DNS_RESOLUTION performs a REAL socket.gethostbyname() call."
echo "   Since DOMAIN_ID is a domain that's merely AVAILABLE (never actually"
echo "   registered/pointed anywhere), this will almost always FAIL to"
echo "   resolve — which correctly keeps the project at VERIFYING_DNS,"
echo "   not READY. That's the all-checks-must-PASS guard working as"
echo "   designed, not a bug. Step 15 below handles this."
PROJECT_STATUS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/" \
  -H "Authorization: Bearer $TOKEN")
echo "$PROJECT_STATUS_RESPONSE"
PROJECT_STATUS=$(extract "$PROJECT_STATUS_RESPONSE" "status")
echo "-> PROJECT_STATUS=$PROJECT_STATUS"

echo
echo "== 11. Request AI domain recommendation (async — dispatch) =="
RECOMMEND_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/$PROJECT_ID/recommend-domain/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN")
echo "$RECOMMEND_RESPONSE"

RECOMMEND_TASK_ID=$(extract "$RECOMMEND_RESPONSE" "task_id")
if [ -z "$RECOMMEND_TASK_ID" ]; then
  echo "!! No task_id returned from recommend-domain, stopping."
  exit 1
fi
echo "-> RECOMMEND_TASK_ID=$RECOMMEND_TASK_ID"

echo
echo "== 11b. Poll domain recommendation task =="
RECOMMEND_TASK_RESULT=$(poll_task "$RECOMMEND_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Domain recommendation task did not complete, stopping."
  exit 1
fi
echo "$RECOMMEND_TASK_RESULT"

RECOMMEND_TASK_STATUS=$(extract "$RECOMMEND_TASK_RESULT" "status")
if [ "$RECOMMEND_TASK_STATUS" != "SUCCESS" ]; then
  echo "!! Domain recommendation task FAILED — check error.code below."
  echo "   Expected AI_GENERATION_FAILED only if Gemini returned malformed"
  echo "   output or hallucinated a domain_id. Anything else is a bug."
else
  RECOMMENDED_DOMAIN=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    result = data.get('result') or {}
    rd = result.get('recommended_domain') or {}
    print(rd.get('domain', ''))
except Exception:
    print('')
" "$RECOMMEND_TASK_RESULT")
  echo "-> Gemini recommended: $RECOMMENDED_DOMAIN"
fi

echo
echo "== 11c. List domain recommendations (should include the one just created, newest first) =="
curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/domain-recommendations/" \
  -H "Authorization: Bearer $TOKEN"

echo
echo
echo "== 12. Check domain for trademark claims (async — dispatch) =="
echo "   Using the already-selected DOMAIN_ID from step 8."
CLAIMS_RESPONSE=$(curl -s -X POST "$BASE_URL/domains/$DOMAIN_ID/check-claims/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN")
echo "$CLAIMS_RESPONSE"

CLAIMS_TASK_ID=$(extract "$CLAIMS_RESPONSE" "task_id")
if [ -z "$CLAIMS_TASK_ID" ]; then
  echo "!! No task_id returned from check-claims, stopping."
  exit 1
fi
echo "-> CLAIMS_TASK_ID=$CLAIMS_TASK_ID"

echo
echo "== 12b. Poll trademark claims task =="
CLAIMS_TASK_RESULT=$(poll_task "$CLAIMS_TASK_ID")
if [ $? -ne 0 ]; then
  echo "!! Trademark claims task did not complete, stopping."
  exit 1
fi
echo "$CLAIMS_TASK_RESULT"

CLAIMS_TASK_STATUS=$(extract "$CLAIMS_TASK_RESULT" "status")
if [ "$CLAIMS_TASK_STATUS" = "SUCCESS" ]; then
  HAS_CLAIMS=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    result = data.get('result') or {}
    print(result.get('has_claims', ''))
except Exception:
    print('')
" "$CLAIMS_TASK_RESULT")
  echo "-> has_claims: $HAS_CLAIMS"
else
  ERROR_CODE=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    err = data.get('error') or {}
    print(err.get('code', ''))
except Exception:
    print('')
" "$CLAIMS_TASK_RESULT")
  echo "!! Trademark claims task FAILED — error.code=$ERROR_CODE"
  echo "   Expect EXTERNAL_API_TIMEOUT or EXTERNAL_API_ERROR here on a"
  echo "   name.com failure, NEVER a SUCCESS with has_claims:false."
fi

echo
echo "== 12c. List domain claims (should include the check just run, newest first) =="
curl -s -X GET "$BASE_URL/domains/$DOMAIN_ID/claims/" \
  -H "Authorization: Bearer $TOKEN"

echo
echo
echo "== 13. Get launch report =="
LAUNCH_REPORT_RESPONSE=$(curl -s -X GET "$BASE_URL/projects/$PROJECT_ID/launch-report/" \
  -H "Authorization: Bearer $TOKEN")
echo "$LAUNCH_REPORT_RESPONSE"

echo
echo
echo "== 14. Ownership checks =="
echo "   A second user must get 404 on the first user's project/domain"
echo "   resources — DomainClaim.domain_result.project.user == request.user"
echo "   and DomainRecommendation.project.user == request.user must both"
echo "   actually be enforced, not just assumed."

echo
echo "== 14a. Register second user (ignore failure if already exists) =="
curl -s -X POST "$BASE_URL/auth/register/" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$OTHER_USERNAME\", \"email\": \"$OTHER_EMAIL\", \"password\": \"$OTHER_PASSWORD\", \"first_name\": \"Other\", \"last_name\": \"User\"}"
echo

echo
echo "== 14b. Login as second user =="
OTHER_LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$OTHER_USERNAME\", \"password\": \"$OTHER_PASSWORD\"}")
echo "$OTHER_LOGIN_RESPONSE"

OTHER_TOKEN=$(extract "$OTHER_LOGIN_RESPONSE" "access")
if [ -z "$OTHER_TOKEN" ]; then
  echo "!! Second user login failed, skipping ownership checks."
else
  echo "-> OTHER_TOKEN acquired"

  echo
  echo "== 14c. Second user GETs first user's domain recommendations — expect HTTP 404 =="
  get_with_status "$BASE_URL/projects/$PROJECT_ID/domain-recommendations/" "$OTHER_TOKEN"

  echo
  echo "== 14d. Second user POSTs recommend-domain on first user's project — expect HTTP 404 =="
  post_with_status "$BASE_URL/projects/$PROJECT_ID/recommend-domain/" "$OTHER_TOKEN"

  echo
  echo "== 14e. Second user GETs first user's domain claims — expect HTTP 404 =="
  get_with_status "$BASE_URL/domains/$DOMAIN_ID/claims/" "$OTHER_TOKEN"

  echo
  echo "== 14f. Second user POSTs check-claims on first user's domain — expect HTTP 404 =="
  post_with_status "$BASE_URL/domains/$DOMAIN_ID/check-claims/" "$OTHER_TOKEN"

  echo
  echo "== 14g. Sanity check: FIRST user still gets HTTP 200 on the same claims GET =="
  get_with_status "$BASE_URL/domains/$DOMAIN_ID/claims/" "$TOKEN"
fi

echo
echo
echo "== 15. Simulate Registration (Feature 5, sandbox-only) =="
echo "   Gated on project.status == READY. If step 10b showed anything"
echo "   other than READY (expected — see note there), this will 409"
echo "   with CONFLICT. That's the correct, intended behavior for a"
echo "   domain whose DNS was never actually configured — not a failure"
echo "   of this script or of Feature 5."
SIMULATE_RESPONSE=$(post_with_status "$BASE_URL/domains/$DOMAIN_ID/simulate-registration/" "$TOKEN")
echo "$SIMULATE_RESPONSE"

SIMULATE_HTTP_CODE=$(echo "$SIMULATE_RESPONSE" | head -n1 | grep -oE '[0-9]+')
if [ "$SIMULATE_HTTP_CODE" = "409" ]; then
  echo "-> 409 CONFLICT as expected (project not READY — see 10b note above)."
  echo "   To manually force a READY state for a full simulate-registration"
  echo "   demo, point DOMAIN_ID's actual DNS A record at any real IP"
  echo "   before running this script, or run check/ again by hand once"
  echo "   you've done so."
elif [ "$SIMULATE_HTTP_CODE" = "202" ]; then
  SIMULATE_BODY=$(echo "$SIMULATE_RESPONSE" | tail -n +2)
  SIMULATE_TASK_ID=$(extract "$SIMULATE_BODY" "task_id")
  echo "-> SIMULATE_TASK_ID=$SIMULATE_TASK_ID"

  echo
  echo "== 15b. Poll simulate-registration task =="
  SIMULATE_TASK_RESULT=$(poll_task "$SIMULATE_TASK_ID")
  if [ $? -ne 0 ]; then
    echo "!! Simulate registration task did not complete (timeout)."
  else
    echo "$SIMULATE_TASK_RESULT"
    SIMULATE_TASK_STATUS=$(extract "$SIMULATE_TASK_RESULT" "status")
    if [ "$SIMULATE_TASK_STATUS" = "SUCCESS" ]; then
      SIMULATE_ORDER_ID=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    result = data.get('result') or {}
    print(result.get('order_id', ''))
except Exception:
    print('')
" "$SIMULATE_TASK_RESULT")
      echo "-> sandbox order_id: $SIMULATE_ORDER_ID"
    else
      ERROR_CODE=$(python3 -c "
import json, sys
try:
    data = json.loads(sys.argv[1])
    err = data.get('error') or {}
    print(err.get('code', ''))
except Exception:
    print('')
" "$SIMULATE_TASK_RESULT")
      echo "!! Simulate registration task FAILED — error.code=$ERROR_CODE"
      echo "   INTERNAL_ERROR here would mean the sandbox guard tripped —"
      echo "   check NAMECOM_TEST_BASE_URL. EXTERNAL_API_TIMEOUT/ERROR means"
      echo "   the name.com sandbox itself had an issue."
    fi
  fi
else
  echo "!! Unexpected HTTP $SIMULATE_HTTP_CODE from simulate-registration/."
fi

echo
echo "== Done =="
echo "PROJECT_ID=$PROJECT_ID"
echo "BRAND_ID=$BRAND_ID"
echo "DOMAIN_ID=$DOMAIN_ID"
echo "RECOMMEND_TASK_ID=$RECOMMEND_TASK_ID"
echo "CLAIMS_TASK_ID=$CLAIMS_TASK_ID"
echo "PROJECT_STATUS_AFTER_DNS=$PROJECT_STATUS"