// frontend/src/api/dns.js

import client from "./client";

// Confirmed against dns/urls.py + dns/views.py + dns/serializers.py:
//   POST /api/v1/domains/{domain_id}/check/               body: {check_types: [...]} -> 202, {domain_id, status: "PROCESSING", task_id}
//   GET  /api/v1/domains/{domain_id}/checks/                                          -> 200, {results: [...]}
//   POST /api/v1/domains/{domain_id}/create-dns-record/    body: {host, type, answer, ttl?, priority?} -> 202, {domain_id, status: "PROCESSING", task_id}
//   GET  /api/v1/domains/{domain_id}/dns-records/                                     -> 200, {results: [Record]}
//                                                            -> 409 CONFLICT if project.status != READY (both DNS record endpoints)
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
//
// create-dns-record/ / dns-records/ (Day 4, Feature 7 — "Point your
// domain") are the real fourth name.com integration: unlike everything
// above, these hit name.com's actual DNS Records API, not a local
// model. create-dns-record/ is ASYNC for consistency with every other
// mutating name.com call in this app, even though a single Create
// Record call is fast — poll GET /tasks/{task_id}/, on SUCCESS
// task.result is the created Record dict directly (no {results: [...]}
// wrapper, since each create produces exactly one record — same
// convention as check-claims/ and simulate-registration/).
// dns-records/ (the list) is the one GET in this app that is NOT a
// local-DB read: there's no model backing DNS records (name.com is the
// only source of truth), so this is a live proxy call and can itself
// fail with EXTERNAL_API_TIMEOUT/EXTERNAL_API_ERROR synchronously,
// unlike every other list endpoint here.
//
// The record `type` dropdown is restricted to A / CNAME on the
// frontend only (see DomainDnsPanel.jsx) — same frontend-only
// narrowing convention as AVAILABLE_CHECK_TYPES below. The backend and
// name.com both support the full type enum.

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

export async function listDnsRecords(domainId) {
  const { data } = await client.get(`domains/${domainId}/dns-records/`);
  return data.results;
}

export async function createDnsRecord(domainId, { host = "", type, answer, ttl = 300, priority }) {
  const body = { host, type, answer, ttl };
  if (priority !== undefined && priority !== null) {
    body.priority = priority;
  }
  const { data } = await client.post(`domains/${domainId}/create-dns-record/`, body);
  return data; // { domain_id, status: "PROCESSING", task_id }
}