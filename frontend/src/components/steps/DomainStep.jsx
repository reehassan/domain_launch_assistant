// frontend/src/components/steps/DomainStep.jsx
//
// Step 02 of the launch flow. "Pick one of several available domains"
// is a browse-and-compare interaction, so results render as a grid of
// DomainCard, not a flat bordered list. The AI recommendation panel
// gets `searchVersion` as a real dependency now (see the fixed
// DomainRecommendationPanel) so regenerating actually clears the stale
// pick instead of silently keeping it on screen.

import { useEffect, useState } from "react";
import { startDomainSearch, listDomainResults, selectDomain } from "../../api/domains";
import { parseApiError } from "../../api/client";
import { useTaskPolling } from "../../hooks/useTaskPolling";
import ErrorBanner from "../ErrorBanner";
import DomainCard from "../DomainCard";
import DomainRecommendationPanel from "../DomainRecommendationPanel";

export default function DomainStep({ project, onProjectUpdate }) {
  const [domains, setDomains] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selectingDomainId, setSelectingDomainId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [searchVersion, setSearchVersion] = useState(0);
  const [claimedDomainIds, setClaimedDomainIds] = useState(() => new Set());
  const domainSearchTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    listDomainResults(project.id)
      .then((data) => mounted && setDomains(data))
      .catch((err) => mounted && setLoadError(parseApiError(err)));
    return () => {
      mounted = false;
      domainSearchTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    if (domainSearchTask.state === "SUCCESS") {
      setDomains(domainSearchTask.result.results);
      setClaimedDomainIds(new Set());
      setSearchVersion((v) => v + 1);
    }
  }, [domainSearchTask.state, domainSearchTask.result]);

  async function handleFindDomains() {
    setActionError(null);
    await domainSearchTask.run(() => startDomainSearch(project.id, project.selected_brand.id));
  }

  async function handleSelectDomain(domainId) {
    setActionError(null);
    setSelectingDomainId(domainId);
    try {
      const result = await selectDomain(project.id, domainId);
      onProjectUpdate({ status: result.status, selected_domain: result.selected_domain });
    } catch (err) {
      setActionError(parseApiError(err));
    } finally {
      setSelectingDomainId(null);
    }
  }

  function handleClaimsChecked(domainId, hasClaims) {
    setClaimedDomainIds((prev) => {
      const next = new Set(prev);
      hasClaims ? next.add(domainId) : next.delete(domainId);
      return next;
    });
  }

  const showFindDomainsButton = domains !== null && domains.length === 0;

  return (
    <div>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError || (domainSearchTask.state === "ERROR" ? domainSearchTask.error : null)} />

      {project.selected_domain && (
        <div className="rounded-sm border-2 border-live/40 bg-live/5 p-3">
          <p className="font-mono text-[10px] uppercase tracking-widest text-live">Selected domain</p>
          <p className="mt-1 font-mono text-2xl font-medium tracking-tight">
            {project.selected_domain.domain}
          </p>
        </div>
      )}

      {domains === null && !loadError && (
        <p className="font-mono text-xs text-ink/40">Loading domain results…</p>
      )}

      {showFindDomainsButton && (
        <button
          onClick={handleFindDomains}
          disabled={domainSearchTask.state === "LOADING"}
          className="rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
        >
          {domainSearchTask.state === "LOADING" ? "Searching…" : "Find Domains"}
        </button>
      )}

      {domains && domains.length > 0 && !project.selected_domain && (
        <>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink/40">
            Pick one to move forward with
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {domains.map((d) => (
              <DomainCard
                key={d.id}
                domain={d}
                isClaimed={claimedDomainIds.has(d.id)}
                selecting={selectingDomainId === d.id}
                onSelect={handleSelectDomain}
                onChecked={handleClaimsChecked}
              />
            ))}
          </div>

          <button
            onClick={handleFindDomains}
            disabled={domainSearchTask.state === "LOADING"}
            className="mt-3 font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink disabled:opacity-50"
          >
            {domainSearchTask.state === "LOADING" ? "Regenerating…" : "Not loving these? Regenerate"}
          </button>

          <div className="mt-3">
            <DomainRecommendationPanel projectId={project.id} triggerKey={searchVersion} />
          </div>
        </>
      )}
    </div>
  );
}
