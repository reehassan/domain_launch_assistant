// frontend/src/pages/LaunchReportPage.jsx
//
// Ticket: "Build the Launch Report page". Standalone route rather than
// a 5th StepRail step (see LaunchStep.jsx / StepRail.jsx) — there's no
// persisted signal marking this "done" (registration itself is never
// persisted, per registration_simulation.py / LaunchStep.jsx's
// `registered` local-state comment), so it doesn't fit StepRail's
// linear done/current/locked model. Reachable at any project status,
// matching the backend LaunchReportView, which is intentionally not
// gated on READY — a mid-flow project just shows more blocking_issues
// instead of a 404.
//
// Read-only, single fetch on mount — no task polling, since
// launch-report/ is synchronous local aggregation (no Celery task
// behind it).
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getLaunchReport } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";
import StampBadge from "../components/StampBadge";
import PerforatedDivider from "../components/PerforatedDivider";

function checkStampStatus(status) {
  if (status === "PASS") return "done";
  if (status === "FAIL" || status === "ERROR") return "error";
  return "loading"; // PENDING
}

export default function LaunchReportPage() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    getLaunchReport(id)
      .then((data) => mounted && setReport(data))
      .catch((err) => mounted && setError(parseApiError(err)));
    return () => {
      mounted = false;
    };
  }, [id]);

  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto my-12 max-w-xl p-4">
        <Link
          to={`/projects/${id}`}
          className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
        >
          ← Back to Project
        </Link>
        <ErrorBanner error={error} />
        {!report && !error && (
          <p className="mt-6 font-mono text-sm text-ink/40">Loading launch report…</p>
        )}
        {report && <ReportBody report={report} />}
      </div>
    </div>
  );
}

function ReportBody({ report }) {
  const { project, brand, domain, claims, checks, readiness } = report;

  return (
    <div className="mt-4 overflow-hidden rounded-sm border-2 border-hairline bg-surface shadow-sm">
      <div className="flex items-center justify-between border-b-2 border-hairline px-6 py-4">
        <div className="flex items-center gap-3">
          <Logo size="sm" withWordmark={false} />
          <h1 className="font-display text-lg font-bold text-ink">{project.name}</h1>
        </div>
        <span className="rounded-sm border border-hairline px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
          {project.status}
        </span>
      </div>

      <div className="px-6 py-5">
        <div className="flex items-center justify-between">
          <p className="font-display text-sm font-bold uppercase tracking-wide">
            <span className="text-ink/30">01</span> Launch Readiness
          </p>
          <StampBadge
            status={readiness.ready ? "done" : "hold"}
            label={readiness.ready ? "Ready" : "Not Ready"}
          />
        </div>
        <div className="mt-2 rounded-sm border border-hairline p-3">
          <p className="font-mono text-2xl font-medium tracking-tight">{readiness.score}%</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-ink/40">
            Domain readiness checks passed
          </p>
        </div>
        {readiness.blocking_issues.length > 0 && (
          <ul className="mt-2 space-y-1">
            {readiness.blocking_issues.map((issue, i) => (
              <li key={i} className="font-mono text-[11px] text-reject">
                • {issue}
              </li>
            ))}
          </ul>
        )}
      </div>

      <PerforatedDivider />

      <div className="px-6 py-5">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">02</span> Brand
        </p>
        {brand ? (
          <div className="mt-2 rounded-sm border border-hairline p-3">
            <p className="font-mono text-lg font-medium tracking-tight">{brand.name}</p>
            <p className="mt-1 text-xs text-ink/70">{brand.description}</p>
          </div>
        ) : (
          <p className="mt-2 font-mono text-xs text-ink/40">No brand selected yet.</p>
        )}
      </div>

      <PerforatedDivider />

      <div className="px-6 py-5">
        <div className="flex items-center justify-between">
          <p className="font-display text-sm font-bold uppercase tracking-wide">
            <span className="text-ink/30">03</span> Domain
          </p>
          {claims && (
            <StampBadge
              status={claims.has_claims ? "error" : "done"}
              label={claims.has_claims ? "Has Claims" : "No Claims"}
            />
          )}
        </div>
        {domain ? (
          <div className="mt-2 rounded-sm border border-hairline p-3">
            <p className="font-mono text-lg font-medium tracking-tight">{domain.domain}</p>
            {domain.purchase_price && (
              <p className="mt-1 text-xs text-ink/60">${domain.purchase_price}/yr</p>
            )}
          </div>
        ) : (
          <p className="mt-2 font-mono text-xs text-ink/40">No domain selected yet.</p>
        )}
      </div>

      <PerforatedDivider />

      <div className="px-6 py-5">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">04</span> Checks
        </p>
        {checks.length > 0 ? (
          <div className="mt-2 space-y-2">
            {checks.map((check) => (
              <div
                key={check.id}
                className="flex items-center justify-between rounded-sm border border-hairline p-3"
              >
                <div>
                  <p className="font-mono text-xs uppercase tracking-wide text-ink/60">
                    {check.check_type}
                  </p>
                  {check.message && (
                    <p className="mt-0.5 text-xs text-ink/70">{check.message}</p>
                  )}
                </div>
                <StampBadge status={checkStampStatus(check.status)} label={check.status} />
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 font-mono text-xs text-ink/40">No checks have been run yet.</p>
        )}
      </div>
    </div>
  );
}