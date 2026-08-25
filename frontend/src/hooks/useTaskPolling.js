// frontend/src/hooks/useTaskPolling.js

import { useCallback, useRef, useState } from "react";
import { getTaskStatus } from "../api/tasks";
import { parseApiError } from "../api/client";

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 30000;

// IDLE    -> nothing started yet
// LOADING -> task dispatched, polling in progress
// SUCCESS -> task.status === "SUCCESS", `result` holds task.result
// ERROR   -> task.status === "FAILURE", or the poll itself failed/timed out
//
// Usage: const { state, result, error, run } = useTaskPolling();
//        await run(() => startDomainSearch(...));  // async fn returning {task_id}
export function useTaskPolling() {
  const [state, setState] = useState("IDLE");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const cancelRef = useRef(false);

  const run = useCallback(async (startFn) => {
    cancelRef.current = false;
    setState("LOADING");
    setResult(null);
    setError(null);

    let taskId;
    try {
      const started = await startFn();
      taskId = started.task_id;
    } catch (err) {
      if (!cancelRef.current) {
        setError(parseApiError(err));
        setState("ERROR");
      }
      return;
    }

    const startedAt = Date.now();

    while (!cancelRef.current) {
      if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
        setError({
          code: "TASK_TIMEOUT",
          message: "This is taking longer than expected. Please try again.",
          details: null,
        });
        setState("ERROR");
        return;
      }

      let task;
      try {
        task = await getTaskStatus(taskId);
      } catch (err) {
        if (!cancelRef.current) {
          setError(parseApiError(err));
          setState("ERROR");
        }
        return;
      }

      if (task.status === "SUCCESS") {
        if (!cancelRef.current) {
          setResult(task.result);
          setState("SUCCESS");
        }
        return;
      }

      if (task.status === "FAILURE") {
        if (!cancelRef.current) {
          setError(task.error ?? {
            code: "UNKNOWN_ERROR",
            message: "The task failed.",
            details: null,
          });
          setState("ERROR");
        }
        return;
      }

      // PENDING or PROCESSING — wait and poll again.
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }, []);

  const cancel = useCallback(() => {
    cancelRef.current = true;
  }, []);

  return { state, result, error, run, cancel };
}