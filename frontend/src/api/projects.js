import client from "./client";
// Confirmed against launches/urls.py + launches/views.py:
//   POST /api/v1/projects/                    create
//   GET  /api/v1/projects/                    list
//   GET  /api/v1/projects/{id}/               retrieve
//   GET  /api/v1/projects/{id}/launch-report/ aggregated summary — see LaunchReportView
// Update/Delete are NOT implemented yet on the backend (Day 1 note:
// "Only Create, List, and Retrieve for Day 1") — do not add UI for
// editing or deleting a project until those views exist.
export async function createProject({ name, business_description }) {
  const { data } = await client.post("projects/", { name, business_description });
  return data;
}
export async function listProjects() {
  const { data } = await client.get("projects/");
  return data.results; // backend wraps list responses in { results: [...] }
}
export async function getProject(id) {
  const { data } = await client.get(`projects/${id}/`);
  return data;
}
export async function getLaunchReport(id) {
  const { data } = await client.get(`projects/${id}/launch-report/`);
  return data;
  // shape: { project: {id, name, status}, brand, domain, claims, checks: [DomainCheck, ...],
  //          readiness: { ready, score, blocking_issues: [...] } }
  // brand/domain/claims are null until selected/checked; reachable at any project status,
  // not just READY — a mid-flow project just shows more blocking_issues.
}