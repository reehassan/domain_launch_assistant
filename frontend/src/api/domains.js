// frontend/src/api/domains.js

import client from "./client";

// Confirmed against domains/urls.py + domains/views.py:
//   POST /api/v1/projects/{id}/domain-search/         body: {brand_idea_id, extensions} -> 202, {search_id, project_id, status: "PROCESSING", task_id}
//   GET  /api/v1/projects/{id}/domains/                optional ?available=&extension=&search= -> 200, {results: [...]}
//   POST /api/v1/projects/{id}/select-domain/          body: {domain_id}                 -> 200, {project_id, selected_domain, status}
//   POST /api/v1/projects/{id}/recommend-domain/                                         -> 202, {task_id, status: "PROCESSING"}
//   GET  /api/v1/projects/{id}/domain-recommendations/                                   -> 200, {results: [DomainRecommendation]} (newest first)
//   POST /api/v1/domains/{id}/check-claims/                                              -> 202, {domain_id, status: "PROCESSING", task_id}
//   GET  /api/v1/domains/{id}/claims/                                                    -> 200, {results: [DomainClaim]} (newest first)
//
// DomainResult shape:         {id, domain, extension, available, status, provider, checked_at}
// DomainRecommendation shape: {id, project_id, recommended_domain: DomainResult, reasoning, created_at}
// DomainClaim shape:          {id, domain_result_id, has_claims, claims_data, checked_at, created_at}
//
// domain-search/ is ASYNC (Day 6): the search row is created PENDING
// synchronously (hence search_id being present immediately), but results
// only exist once the Celery task finishes. Poll GET /tasks/{task_id}/ —
// on SUCCESS, task.result is { search_id, status, results: [DomainResult] }.
//
// recommend-domain/ is ASYNC (Day 2, Feature 3) for the same reason: it's a
// live Gemini call. Poll GET /tasks/{task_id}/ — on SUCCESS, task.result
// is the single DomainRecommendation object (not wrapped in {results: [...]},
// since each generate/regenerate produces exactly one new row).
//
// check-claims/ is ASYNC (Day 2, Feature 4) for the same reason: it's a
// live name.com call. Poll GET /tasks/{task_id}/ — on SUCCESS, task.result
// is the single DomainClaim object (not wrapped in {results: [...]}, since
// each check produces exactly one new row).

const DEFAULT_EXTENSIONS = [".com", ".ai", ".io"];

export async function startDomainSearch(projectId, brandIdeaId, extensions = DEFAULT_EXTENSIONS) {
  const { data } = await client.post(
    `projects/${projectId}/domain-search/`,
    { brand_idea_id: brandIdeaId, extensions }
  );
  return data; // { search_id, project_id, status, task_id }
}

export async function listDomainResults(projectId, filters = {}) {
  const { data } = await client.get(`projects/${projectId}/domains/`, {
    params: filters,
  });
  return data.results;
}

export async function selectDomain(projectId, domainId) {
  const { data } = await client.post(
    `projects/${projectId}/select-domain/`,
    { domain_id: domainId }
  );
  return data;
}

export async function recommendDomain(projectId) {
  const { data } = await client.post(`projects/${projectId}/recommend-domain/`);
  return data; // { task_id, status }
}

export async function getDomainRecommendations(projectId) {
  const { data } = await client.get(`projects/${projectId}/domain-recommendations/`);
  return data.results; // [DomainRecommendation, ...], newest first
}

export async function checkDomainClaims(domainId) {
  const { data } = await client.post(`domains/${domainId}/check-claims/`);
  return data; // { domain_id, status, task_id }
}

export async function listDomainClaims(domainId) {
  const { data } = await client.get(`domains/${domainId}/claims/`);
  return data.results; // [DomainClaim, ...], newest first
}