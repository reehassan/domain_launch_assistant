// frontend/src/api/dns.js

import client from "./client";

// Confirmed against dns/urls.py + dns/views.py + dns/serializers.py:
//   POST /api/v1/domains/{domain_id}/check/   body: {check_types: [...]} -> 202, {domain_id, status: "PROCESSING", task_id}
//   GET  /api/v1/domains/{domain_id}/checks/                              -> 200, {results: [...]}
//
// {domain_id} is DomainResult.id — ownership enforced backend-side via
// domain_result.project.user, no project_id in the URL.
//
// check/ is now ASYNC (Day 6): DomainCheck rows are created PENDING
// synchronously, task_id is a real dispatched Celery task_id (no longer
// a throwaway uuid4 — that placeholder is gone). Poll GET /tasks/{task_id}/ —
// on SUCCESS, task.result is { results: [DomainCheck] }.
//
// DNS_CONFIGURATION is a valid backend CheckType but withheld from the
// frontend this iteration — enforced here, not by the backend.
//
// DNS_RESOLUTION withheld as of Day 3 (Feature 5/6 hardening): it does a
// real socket.gethostbyname() lookup, which can only ever PASS for a
// domain that's actually registered and pointed somewhere. Since domain
// registration in this app is sandbox-simulated (Feature 5) and happens
// AFTER a project reaches READY, DNS_RESOLUTION could never pass before
// READY — making READY structurally unreachable. DOMAIN_READINESS (is
// this the project's selected, available domain) is the check that's
// actually meaningful pre-registration. The backend check_type and
// handler are untouched — this is a frontend-only decision about which
// checks this flow requests.

export const AVAILABLE_CHECK_TYPES = ["DOMAIN_READINESS"];

export async function runChecks(domainId, checkTypes = AVAILABLE_CHECK_TYPES) {
  const { data } = await client.post(`domains/${domainId}/check/`, {
    check_types: checkTypes,
  });
  return data; // { domain_id, status, task_id }
}

export async function listChecks(domainId) {
  const { data } = await client.get(`domains/${domainId}/checks/`);
  return data.results;
}