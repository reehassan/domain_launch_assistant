// frontend/src/components/DomainRecommendationPanel.jsx
//
// "We'd pick X because Y" panel for Feature 3 (AI domain recommendation).
// On mount, fetches the latest existing DomainRecommendation for the
// project (if any) via GET /domain-recommendations/, so a page refresh
// shows the last pick without re-calling Gemini. The button re-POSTs
// /recommend-domain/ and, once the task succeeds, replaces the shown
// recommendation with the new one.
//
// FIX: `triggerKey` was previously accepted by the caller but never
// destructured or read here, so a domain-search regenerate silently did
// NOT refresh the recommendation despite the calling code (and its own
// comments) implying it would. It's now watched explicitly: whenever it
// changes, we clear the stale recommendation so the old pick can't be
// shown against a domain list that's already been replaced.
//
// Owns its own useTaskPolling() instance, same reasoning as
// DomainClaimsCheck.jsx: this panel's in-flight request shouldn't be
// tangled with any other section's loading state.

import { useEffect, useRef, useState } from "react";
import { recommendDomain, getDomainRecommendations } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import { parseApiError } from "../api/client";
import StampBadge from "./StampBadge";

export default function DomainRecommendationPanel({ projectId, triggerKey }) {
  const [recommendation, setRecommendation] = useState(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [initialError, setInitialError] = useState(null);
  const isFirstRun = useRef(true);

  const recommendTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;

    // On the very first mount, load whatever recommendation already
    // exists. On any later change of triggerKey (a domain search just
    // regenerated the list this recommendation was based on), drop the
    // stale pick instead of re-fetching — it no longer matches what's
    // on screen, and the founder should press the button to re-run it.
    if (isFirstRun.current) {
      isFirstRun.current = false;
      setLoadingInitial(true);
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
    } else {
      setRecommendation(null);
      recommendTask.cancel();
    }

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, triggerKey]);

  useEffect(() => {
    if (recommendTask.state === "SUCCESS" && recommendTask.result) {
      setRecommendation(recommendTask.result);
    }
     
  }, [recommendTask.state, recommendTask.result]);

  async function handleRecommend() {
    await recommendTask.run(() => recommendDomain(projectId));
  }

  const isLoading = recommendTask.state === "LOADING";

  return (
    <div className="rounded-sm border-2 border-wire/40 bg-elevated p-3">
      <div className="flex items-center justify-between">
        <p className="font-mono text-[10px] uppercase tracking-widest text-wire">
          ✦ AI Recommendation
        </p>
        {recommendation && <StampBadge status="done" label="Stamped" />}
      </div>

      {loadingInitial && (
        <p className="mt-2 font-mono text-xs text-ink/40">Loading recommendation…</p>
      )}

      {recommendation && (
        <div className="mt-2">
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
