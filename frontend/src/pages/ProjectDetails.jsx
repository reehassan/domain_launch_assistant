// frontend/src/pages/ProjectDetails.jsx — stepper rewrite
//
// STRUCTURAL CHANGE from the old version: this used to be one ~400-line
// component owning brand/domain/checks/claims data, three
// useTaskPolling instances, and every section's render logic at once,
// with all four sections rendered in a single long scroll gated by
// nested conditionals. That made the flow's actual shape (a 4-step
// wizard with irreversible progression) invisible in the UI — you could
// only tell where you were by scrolling and reading stamp badges, and
// there was no way to jump back to a completed step, and a bug like a
// dead `triggerKey` prop had nowhere obvious to get caught.
//
// Now: this shell does exactly three things.
//   1. Fetches `project` and owns the single source of truth for it.
//   2. Derives which step is the "frontier" (the first not-yet-done
//      step) purely from project fields — no parallel client-side
//      status tracking to keep in sync by hand.
//   3. Renders the StepRail plus exactly one step component. Each step
//      component fetches its own data, owns its own task polling, and
//      only ever talks back up through onProjectUpdate.
//
// `viewIndex` lets the founder click a completed step in the rail to
// look back at it without losing their place — it's cleared (falls
// back to following the frontier) any time the project actually
// advances, so completing an action always jumps forward again.

import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getProject } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";
import StepRail from "../components/StepRail";
import BrandStep from "../components/steps/BrandStep";
import DomainStep from "../components/steps/DomainStep";
import VerifyStep from "../components/steps/VerifyStep";
import LaunchStep from "../components/steps/LaunchStep";

const STEPS = [
  { key: "brand", label: "Brand", Component: BrandStep },
  { key: "domain", label: "Domain", Component: DomainStep },
  { key: "verify", label: "Verify", Component: VerifyStep },
  { key: "launch", label: "Launch", Component: LaunchStep },
];

function frontierIndexFor(project) {
  if (!project.selected_brand) return 0;
  if (!project.selected_domain) return 1;
  if (project.status !== "READY") return 2;
  return 3;
}

export default function ProjectDetails() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [error, setError] = useState(null);
  const [viewIndex, setViewIndex] = useState(null); // null = follow the frontier

  useEffect(() => {
    let mounted = true;
    getProject(id)
      .then((p) => mounted && setProject(p))
      .catch((err) => mounted && setError(parseApiError(err)));
    return () => {
      mounted = false;
    };
  }, [id]);

  function handleProjectUpdate(patch) {
    setProject((prev) => ({ ...prev, ...patch }));
    setViewIndex(null); // an action just landed — jump forward to the new frontier
  }

  return (
    <div className="min-h-screen bg-paper">
      <div className="mx-auto my-12 max-w-xl p-4">
        <Link
          to="/dashboard"
          className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
        >
          ← Back to Dashboard
        </Link>

        <ErrorBanner error={error} />

        {!project && !error && (
          <p className="mt-6 font-mono text-sm text-ink/40">Loading manifest…</p>
        )}

        {project && (
          <ProjectDetailsBody
            project={project}
            viewIndex={viewIndex}
            setViewIndex={setViewIndex}
            onProjectUpdate={handleProjectUpdate}
          />
        )}
      </div>
    </div>
  );
}

function ProjectDetailsBody({ project, viewIndex, setViewIndex, onProjectUpdate }) {
  const frontierIndex = frontierIndexFor(project);
  const activeIndex = viewIndex ?? frontierIndex;
  const ActiveStep = STEPS[activeIndex].Component;

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

      <div className="border-b-2 border-hairline px-6 py-3">
        <p className="text-sm text-ink/80">{project.business_description}</p>
      </div>

      <StepRail
        steps={STEPS}
        frontierIndex={frontierIndex}
        viewIndex={activeIndex}
        onSelect={(key) => setViewIndex(STEPS.findIndex((s) => s.key === key))}
      />

      <div className="px-6 py-5">
        {viewIndex !== null && viewIndex !== frontierIndex && (
          <button
            onClick={() => setViewIndex(null)}
            className="mb-3 font-mono text-[11px] uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
          >
            ← Back to current step
          </button>
        )}
        <ActiveStep project={project} onProjectUpdate={onProjectUpdate} />
      </div>
    </div>
  );
}
