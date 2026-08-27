// frontend/src/components/DomainRecommendationPanel.jsx
//
// "We'd pick X because Y" panel for Feature 3 (AI domain recommendation).
// On mount, fetches the latest existing DomainRecommendation for the
// project (if any) via GET /domain-recommendations/, so a page refresh
// shows the last pick without re-calling Gemini. The button re-POSTs
// /recommend-domain/ and, once the task succeeds, replaces the shown
// recommendation with the new one — same latest-by-created_at convention
// the brand/domain "Regenerate" buttons already use elsewhere in this file.
//
// Owns its own useTaskPolling() instance, same reasoning as
// DomainClaimsCheck.jsx: this panel's in-flight request shouldn't be
// tangled with any other section's loading state.

import { useEffect, useState } from "react";
import { recommendDomain, getDomainRecommendations } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import { parseApiError } from "../api/client";
import StampBadge from "./StampBadge";

export default function DomainRecommendationPanel({ projectId }) {
  const [recommendation, setRecommendation] = useState(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [initialError, setInitialError] = useState(null);

  const recommendTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    getDomainRecommendations(projectId)
      .then((results) => {
        if (!mounted) return;
        setRecommendation(results[0] ?? null);
      })
      .catch((err) => {
        if (mounted) setInitialError(parseApiError(err));
      })
      .finally(() => {
        if (mounted) setLoadingInitial(false);
      });
    return () => {
      mounted = false;
      recommendTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (recommendTask.state === "SUCCESS" && recommendTask.result) {
      setRecommendation(recommendTask.result);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recommendTask.state, recommendTask.result]);

  async function handleRecommend() {
    await recommendTask.run(() => recommendDomain(projectId));
  }

  const isLoading = recommendTask.state === "LOADING";

  return (
    <div className="px-6 py-5">
      <div className="flex items-center justify-between">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">03</span> AI Recommendation
        </p>
        {recommendation && <StampBadge status="done" label="Stamped" />}
      </div>

      {loadingInitial && (
        <p className="mt-2 font-mono text-xs text-ink/40">Loading recommendation…</p>
      )}

      {recommendation && (
        <div className="mt-2 rounded-sm border border-hairline p-3">
          <p className="font-mono text-lg font-medium tracking-tight">
            {recommendation.recommended_domain.domain}
          </p>
          <p className="mt-1 text-xs text-ink/60">{recommendation.reasoning}</p>
        </div>
      )}

      <button
        onClick={handleRecommend}
        disabled={isLoading}
        className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
      >
        {isLoading ? "Thinking…" : recommendation ? "Regenerate" : "Get AI Recommendation"}
      </button>

      {recommendTask.state === "ERROR" && recommendTask.error && (
        <p className="mt-2 font-mono text-[11px] text-reject">{recommendTask.error.message}</p>
      )}
      {initialError && (
        <p className="mt-2 font-mono text-[11px] text-reject">{initialError.message}</p>
      )}
    </div>
  );
}