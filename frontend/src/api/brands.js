import client from "./client";

// Confirmed against brands/urls.py + brands/views.py:
//   POST /api/v1/projects/{id}/generate-brands/   body: {count?}   -> 202, {task_id, status: "PROCESSING"}
//   GET  /api/v1/projects/{id}/brands/                              -> 200, array of BrandIdea
//   POST /api/v1/projects/{id}/select-brand/       body: {brand_id} -> 200, {project_id, selected_brand, status}
//
// BrandIdea shape: {id, project, name, description, is_selected, created_at}
//
// generate-brands/ is now ASYNC (Day 6): returns 202 immediately, actual
// brand generation happens in a Celery task. Poll GET /tasks/{task_id}/
// (see hooks/useTaskPolling.js) — on SUCCESS, task.result is the array
// of BrandIdea objects, same shape the old synchronous 201 used to return
// directly.


export async function generateBrands(projectId, count) {
  const body = count ? { count } : {};
  const { data } = await client.post(
    `projects/${projectId}/generate-brands/`,
    body
  );
  return data;
}

export async function listBrands(projectId) {
  const { data } = await client.get(`projects/${projectId}/brands/`);
  return data;
}

export async function selectBrand(projectId, brandId) {
  const { data } = await client.post(
    `projects/${projectId}/select-brand/`,
    { brand_id: brandId }
  );
  return data;
}