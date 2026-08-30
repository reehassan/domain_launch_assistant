// frontend/src/components/steps/DomainStep.jsx
//
// Step 02 of the launch flow. "Pick one of several available domains"
// is a browse-and-compare interaction, so results render as a grid of
// DomainCard, not a flat bordered list. The AI recommendation panel
// gets `searchVersion` as a real dependency now (see the fixed
// DomainRecommendationPanel) so regenerating actually clears the stale
// pick instead of silently keeping it on screen.
//
// claimStatusByDomainId (Ticket 6) tracks each domain's trademark
// claims check as "CHECKING" | "CLEAR" | "CLAIMED" | "ERROR" |
// undefined, reported up from each card's DomainClaimsCheck (which now
// runs automatically on mount instead of waiting for a click). This
// replaced a plain claimedDomainIds Set: a Set can only say "yes/no
// claimed", which meant a domain whose check hadn't run yet — or was
// still in flight — read identically to "confirmed clear", so Select
// was reachable before any check had actually completed.
//
// Extension picker: mirrors VALID_EXTENSIONS in domains/serializers.py
// (backend supports 8, the old default only ever requested 3 —
// .com/.ai/.io — so .net/.org/.co/.dev/.app were never offered even
// though the API already accepted them). selectedExtensions is passed
// explicitly into startDomainSearch() instead of relying on that
// module's DEFAULT_EXTENSIONS fallback.
import { useEffect, useState } from "react";
import { startDomainSearch, listDomainResults, selectDomain } from "../../api/domains";
import { parseApiError } from "../../api/client";
import { useTaskPolling } from "../../hooks/useTaskPolling";
import ErrorBanner from "../ErrorBanner";
import DomainCard from "../DomainCard";
import DomainRecommendationPanel from "../DomainRecommendationPanel";

const ALL_EXTENSIONS = [".com", ".ai", ".io", ".net", ".org", ".co", ".dev", ".app"];
const DEFAULT_SELECTED_EXTENSIONS = [".com", ".ai", ".io"];

export default function DomainStep({ project, onProjectUpdate }) {
  const [domains, setDomains] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selectingDomainId, setSelectingDomainId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [searchVersion, setSearchVersion] = useState(0);
  const [claimStatusByDomainId, setClaimStatusByDomainId] = useState(() => ({}));
  const [selectedExtensions, setSelectedExtensions] = useState(() => DEFAULT_SELECTED_EXTENSIONS);
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
      setClaimStatusByDomainId({});
      setSearchVersion((v) => v + 1);
    }
  }, [domainSearchTask.state, domainSearchTask.result]);
  function toggleExtension(ext) {
    setSelectedExtensions((prev) =>
      prev.includes(ext) ? prev.filter((e) => e !== ext) : [...prev, ext]
    );
  }
  async function handleFindDomains() {
    setActionError(null);
    await domainSearchTask.run(() =>
      startDomainSearch(project.id, project.selected_brand.id, selectedExtensions)
    );
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
  function handleClaimsChecked(domainId, claimStatus) {
    setClaimStatusByDomainId((prev) => ({ ...prev, [domainId]: claimStatus }));
  }
  const showFindDomainsButton = domains !== null && domains.length === 0;
  const findDomainsDisabled = domainSearchTask.state === "LOADING" || selectedExtensions.length === 0;
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
        <>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink/40">
            Extensions to search
          </p>
          <div className="mb-3 flex flex-wrap gap-2">
            {ALL_EXTENSIONS.map((ext) => {
              const active = selectedExtensions.includes(ext);
              return (
                <button
                  key={ext}
                  type="button"
                  onClick={() => toggleExtension(ext)}
                  className={`rounded-sm border-2 px-2 py-1 font-mono text-xs uppercase tracking-wide transition ${
                    active
                      ? "border-signal bg-signal/10 text-signal"
                      : "border-ink/20 text-ink/40 hover:text-ink"
                  }`}
                >
                  {ext}
                </button>
              );
            })}
          </div>
          <button
            onClick={handleFindDomains}
            disabled={findDomainsDisabled}
            className="rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
          >
            {domainSearchTask.state === "LOADING" ? "Searching…" : "Find Domains"}
          </button>
        </>
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
                claimStatus={claimStatusByDomainId[d.id]}
                selecting={selectingDomainId === d.id}
                onSelect={handleSelectDomain}
                onChecked={handleClaimsChecked}
              />
            ))}
          </div>
          <button
            onClick={handleFindDomains}
            disabled={findDomainsDisabled}
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