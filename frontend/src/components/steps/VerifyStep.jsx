// frontend/src/components/steps/VerifyStep.jsx
//
// Step 03 of the launch flow. Unlike Brand/Domain (pick one of several
// options -> grid), this step is "review a linear checklist" -> plain
// list. Different content shape, different layout, on purpose.

import { useEffect, useState } from "react";
import { runChecks, listChecks, AVAILABLE_CHECK_TYPES } from "../../api/dns";
import { listDomainClaims } from "../../api/domains";
import { getProject } from "../../api/projects";
import { parseApiError } from "../../api/client";
import { useTaskPolling } from "../../hooks/useTaskPolling";
import { latestChecksByType } from "../../utils/checks";
import ErrorBanner from "../ErrorBanner";
import StampBadge from "../StampBadge";

export default function VerifyStep({ project, onProjectUpdate }) {
  const [checks, setChecks] = useState(null);
  const [claim, setClaim] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const dnsCheckTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    Promise.all([listChecks(project.selected_domain.id), listDomainClaims(project.selected_domain.id)])
      .then(([checksResult, claimsResult]) => {
        if (!mounted) return;
        setChecks(checksResult);
        setClaim(claimsResult[0] ?? null);
      })
      .catch((err) => mounted && setLoadError(parseApiError(err)));
    return () => {
      mounted = false;
      dnsCheckTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.selected_domain.id]);

  useEffect(() => {
    if (dnsCheckTask.state === "SUCCESS") {
      setChecks(dnsCheckTask.result.results);
      // Running checks can flip project.status to READY server-side, but
      // the check endpoint's own response never carries that back — so
      // the shell needs a fresh copy of the project to unlock step 04.
      getProject(project.id)
        .then((p) => onProjectUpdate({ status: p.status }))
        .catch((err) => setLoadError(parseApiError(err)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dnsCheckTask.state, dnsCheckTask.result]);

  async function handleRunChecks() {
    setLoadError(null);
    await dnsCheckTask.run(() => runChecks(project.selected_domain.id));
  }

  const latestChecks = checks ? latestChecksByType(checks) : [];

  return (
    <div>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={dnsCheckTask.state === "ERROR" ? dnsCheckTask.error : null} />

      <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">Domain</p>
      <p className="mt-1 font-mono text-lg">{project.selected_domain.domain}</p>

      {claim && (
        <div className="mt-3 rounded-sm border border-hairline p-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-ink/60">Trademark</span>
            <StampBadge
              status={claim.has_claims ? "hold" : "done"}
              label={claim.has_claims ? "Potential Claim" : "No Claims"}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] text-ink/40">
            This automated check is informational and does not constitute legal advice.
          </p>
        </div>
      )}

      <button
        onClick={handleRunChecks}
        disabled={dnsCheckTask.state === "LOADING"}
        className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
      >
        {dnsCheckTask.state === "LOADING" ? "Running…" : "Run Checks"}
      </button>

      {checks === null && !loadError && (
        <p className="mt-3 font-mono text-xs text-ink/40">Loading checks…</p>
      )}

      {checks && checks.length === 0 && (
        <p className="mt-3 font-mono text-xs text-ink/40">
          No checks run yet — run checks to verify this domain is ready to launch.
        </p>
      )}

      {latestChecks.length > 0 && (
        <ul className="mt-3 space-y-2">
          {AVAILABLE_CHECK_TYPES.map((type) => {
            const c = latestChecks.find((row) => row.check_type === type);
            const rowStatus = !c
              ? "pending"
              : c.status === "PASS"
              ? "done"
              : c.status === "FAIL"
              ? "error"
              : c.status === "ERROR"
              ? "hold"
              : "pending";
            return (
              <li
                key={type}
                className="flex items-center justify-between rounded-sm border border-hairline p-3"
              >
                <div>
                  <span className="font-mono text-sm">{type.replace(/_/g, " ")}</span>
                  {c?.message && <p className="mt-1 text-xs text-ink/50">{c.message}</p>}
                </div>
                <StampBadge status={rowStatus} label={c?.status ?? "Not run"} />
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
