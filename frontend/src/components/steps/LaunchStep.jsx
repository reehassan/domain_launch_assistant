// frontend/src/components/steps/LaunchStep.jsx
//
// Step 04/05 of the launch flow. DomainCheckoutPanel handles
// registration (Feature 6); DomainDnsPanel (Feature 7, added here)
// handles pointing the domain somewhere via name.com's real DNS
// Records API — the fourth genuinely distinct name.com endpoint family
// in this app, after availability, claims, and registration.
//
// `registered` is local, same-session state set via
// DomainCheckoutPanel's onRegistered callback — there's no backend
// field for "was this domain actually registered" to read instead
// (registration_simulation.py deliberately persists nothing), so this
// mirrors the same limitation checkout itself already accepts rather
// than inventing a new source of truth.
//
// Launch Report link: always shown, not just once registered — the
// report itself is reachable at any project status (see
// LaunchReportPage.jsx / backend LaunchReportView), so a founder can
// jump to it to see current progress/blocking issues even before
// finishing this step.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import DomainCheckoutPanel from "../DomainCheckoutPanel";
import DomainDnsPanel from "../DomainDnsPanel";
import PerforatedDivider from "../PerforatedDivider";
import StampBadge from "../StampBadge";
export default function LaunchStep({ project }) {
  const { id } = useParams();
  const [registered, setRegistered] = useState(false);
  return (
    <div>
      <DomainCheckoutPanel
        domain={project.selected_domain}
        onRegistered={() => setRegistered(true)}
      />
      {registered && (
        <>
          <PerforatedDivider />
          <DomainDnsPanel domain={project.selected_domain} />
        </>
      )}
      <div className="mt-4 flex flex-col items-center gap-3 pt-2 text-center">
        <StampBadge status="done" label="Ready to Launch" />
        <Link
          to={`/projects/${id}/report`}
          className="rounded-sm border border-hairline px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-ink/70 transition hover:bg-hairline/20"
        >
          View Launch Report
        </Link>
      </div>
    </div>
  );
}