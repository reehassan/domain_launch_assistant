// frontend/src/api/domains.js

import client from "./client";

// Confirmed against domains/urls.py + domains/views.py:
//   POST /api/v1/projects/{id}/domain-search/   body: {brand_idea_id, extensions} -> 202, {search_id, project_id, status: "PROCESSING", task_id}
//   GET  /api/v1/projects/{id}/domains/          optional ?available=&extension=&search= -> 200, {results: [...]}
//   POST /api/v1/projects/{id}/select-domain/    body: {domain_id}                 -> 200, {project_id, selected_domain, status}
//
// DomainResult shape: {id, domain, extension, available, status, provider, checked_at}
//
// domain-search/ is now ASYNC (Day 6): the search row is created PENDING
// synchronously (hence search_id being present immediately), but results
// only exist once the Celery task finishes. Poll GET /tasks/{task_id}/ —
// on SUCCESS, task.result is { search_id, status, results: [DomainResult] }.

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