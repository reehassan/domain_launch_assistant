// frontend/src/components/steps/LaunchStep.jsx
//
// Step 04/05 of the launch flow. DomainCheckoutPanel handles
// registration (Feature 6); DomainDnsPanel (Feature 7) handles
// pointing the domain somewhere via name.com's real DNS Records API.
//
// Persistence fix (post-Ticket 15): `registered` used to be pure local
// state, reset to false on every remount — meaning navigating to the
// Launch Report page and back (a route change, which unmounts this
// component) made an already-registered domain look unregistered
// again. It's now lazily seeded from the persisted
// project.selected_domain.registered_at field (see domains/tasks.py +
// DomainResultSerializer) on mount, so a fresh mount correctly reflects
// reality. The onRegistered callback is kept for the same-session case
// — clicking "Complete Purchase" right now still reveals DomainDnsPanel
// immediately, without needing a project refetch.
//
// Celebration: a genuine "just registered this session" event
// (onJustRegistered, distinct from onRegistered — see
// DomainCheckoutPanel's comment) triggers the same mascot + modal
// moment used on login, so completing the actual six-step flow this
// app exists for gets the visual payoff it deserves, not just a static
// StampBadge.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import DomainCheckoutPanel from "../DomainCheckoutPanel";
import DomainDnsPanel from "../DomainDnsPanel";
import PerforatedDivider from "../PerforatedDivider";
import StampBadge from "../StampBadge";
import LaunchSuccessModal from "../LaunchSuccessModal";

export default function LaunchStep({ project }) {
  const { id } = useParams();
  const [registered, setRegistered] = useState(
    () => Boolean(project.selected_domain?.registered_at)
  );
  const [showCelebration, setShowCelebration] = useState(false);

  function handleJustRegistered() {
    setShowCelebration(true);
    setTimeout(() => setShowCelebration(false), 2200);
  }

  return (
    <div>
      <LaunchSuccessModal
        show={showCelebration}
        title="Your domain is live 🚀"
        subtitle="Point it somewhere below to finish launching."
      />

      <DomainCheckoutPanel
        domain={project.selected_domain}
        onRegistered={() => setRegistered(true)}
        onJustRegistered={handleJustRegistered}
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