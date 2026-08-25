// frontend/src/api/tasks.js

import client from "./client";

// Corresponds to GET /api/v1/tasks/{task_id}/ (domain_launch_assistant/tasks).
// Response shape: { task_id, status, result, error }
//   status: "PENDING" | "PROCESSING" | "SUCCESS" | "FAILURE"
//   result: present only on SUCCESS — shape varies by task (see brands.js/
//           domains.js/dns.js task result shapes)
//   error: { code, message } | null — present only on FAILURE

export async function getTaskStatus(taskId) {
  const { data } = await client.get(`tasks/${taskId}/`);
  return data;
}