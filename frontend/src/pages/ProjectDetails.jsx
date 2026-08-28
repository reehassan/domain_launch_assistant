// frontend/src/pages/ProjectDetails.jsx — Day 7, boarding-pass dashboard
//
// Changes from the previous version:
//   - DomainRecommendationPanel now lives inside the Domain (02) section,
//     alongside the results list — not as a separate section after
//     selection. It auto-fires via `searchVersion`, which this component
//     bumps every time a domain search (initial or regenerate) succeeds.
//   - claimedDomainIds tracks which rows came back with has_claims:true
//     (reported via DomainClaimsCheck's onChecked callback) and disables
//     that row's "Select" button, with a note pointing back at the list.
//   - Day 3 (Feature 6): added a 04 Checkout section — DomainCheckoutPanel
//     — shown once project.status === "READY" and a domain is selected.
//     On-platform cart/checkout backed by the existing sandbox-only
//     simulate-registration endpoint (no real payment, no real name.com
//     purchase). Placed after Readiness, before the final seal.
//   - FIX (Day 3, readiness/checkout desync): running DNS/domain checks
//     can flip LaunchProject.status to READY server-side (in
//     run_domain_checks_task), but the check endpoint's response is just
//     {results: [DomainCheck]} — it never carries the updated project
//     status back. Without a refetch, local `project.status` goes stale
//     the moment checks pass, so the Checkout gate (project.status ===
//     "READY") never opens even though the backend is already READY.
//     Refetching the project on dnsCheckTask SUCCESS closes that gap.
// Everything else (brand flow, readiness flow) is unchanged from Day 7.
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getProject } from "../api/projects";
import { generateBrands, listBrands, selectBrand } from "../api/brands";
import { startDomainSearch, listDomainResults, selectDomain } from "../api/domains";
import { runChecks, listChecks, AVAILABLE_CHECK_TYPES } from "../api/dns";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import StampBadge from "../components/StampBadge";
import PerforatedDivider from "../components/PerforatedDivider";
import { latestChecksByType } from "../utils/checks";
import { useTaskPolling } from "../hooks/useTaskPolling";
import DomainClaimsCheck from "../components/DomainClaimsCheck";
import DomainRecommendationPanel from "../components/DomainRecommendationPanel";
import DomainCheckoutPanel from "../components/DomainCheckoutPanel";
export default function ProjectDetails() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [brands, setBrands] = useState(null);
  const [domains, setDomains] = useState(null);
  const [checks, setChecks] = useState(null);
  const [error, setError] = useState(null);
  const [selectingId, setSelectingId] = useState(null);
  const [selectingDomainId, setSelectingDomainId] = useState(null);
  const [searchVersion, setSearchVersion] = useState(0);
  const [claimedDomainIds, setClaimedDomainIds] = useState(() => new Set());
  const brandGenTask = useTaskPolling();
  const domainSearchTask = useTaskPolling();
  const dnsCheckTask = useTaskPolling();
  useEffect(() => {
    let mounted = true;
    getProject(id)
      .then((p) => {
        if (!mounted) return;
        setProject(p);
        const calls = [listBrands(id), listDomainResults(id)];
        if (p.selected_domain) {
          calls.push(listChecks(p.selected_domain.id));
        }
        return Promise.all(calls);
      })
      .then((results) => {
        if (!mounted || !results) return;
        const [brandsResult, domainsResult, checksResult] = results;
        setBrands(brandsResult);
        setDomains(domainsResult);
        if (checksResult) setChecks(checksResult);
      })
      .catch((err) => {
        if (mounted) setError(parseApiError(err));
      });
    return () => {
      mounted = false;
      brandGenTask.cancel();
      domainSearchTask.cancel();
      dnsCheckTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
  async function handleGenerate() {
    setError(null);
    await brandGenTask.run(() => generateBrands(id));
  }
  useEffect(() => {
    if (brandGenTask.state === "SUCCESS") {
      setBrands(brandGenTask.result);
    } else if (brandGenTask.state === "ERROR") {
      setError(brandGenTask.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brandGenTask.state, brandGenTask.result, brandGenTask.error]);
  async function handleSelect(brandId) {
    setError(null);
    setSelectingId(brandId);
    try {
      const result = await selectBrand(id, brandId);
      setProject((prev) => ({ ...prev, status: result.status, selected_brand: result.selected_brand }));
      setBrands((prev) => prev.map((b) => ({ ...b, is_selected: b.id === brandId })));
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSelectingId(null);
    }
  }
  async function handleFindDomains() {
    setError(null);
    await domainSearchTask.run(() => startDomainSearch(id, project.selected_brand.id));
  }
  useEffect(() => {
    if (domainSearchTask.state === "SUCCESS") {
      setDomains(domainSearchTask.result.results);
      setClaimedDomainIds(new Set());
      setSearchVersion((v) => v + 1);
    } else if (domainSearchTask.state === "ERROR") {
      setError(domainSearchTask.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainSearchTask.state, domainSearchTask.result, domainSearchTask.error]);
  async function handleSelectDomain(domainId) {
    setError(null);
    setSelectingDomainId(domainId);
    try {
      const result = await selectDomain(id, domainId);
      setProject((prev) => ({ ...prev, status: result.status, selected_domain: result.selected_domain }));
      setChecks(null);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSelectingDomainId(null);
    }
  }
  function handleClaimsChecked(domainId, hasClaims) {
    setClaimedDomainIds((prev) => {
      const next = new Set(prev);
      if (hasClaims) {
        next.add(domainId);
      } else {
        next.delete(domainId);
      }
      return next;
    });
  }
  async function handleRunChecks() {
    setError(null);
    await dnsCheckTask.run(() => runChecks(project.selected_domain.id));
  }
  useEffect(() => {
    if (dnsCheckTask.state === "SUCCESS") {
      setChecks(dnsCheckTask.result.results);
      // FIX: the check task's response never carries project.status —
      // it's mutated server-side inside run_domain_checks_task, not
      // returned here. Refetch so a READY transition (all requested
      // checks PASSed) actually reaches local state and opens Checkout.
      getProject(id)
        .then(setProject)
        .catch((err) => setError(parseApiError(err)));
    } else if (dnsCheckTask.state === "ERROR") {
      setError(dnsCheckTask.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dnsCheckTask.state, dnsCheckTask.result, dnsCheckTask.error]);
  const showGenerateButton =
    project?.status === "DRAFT" && brands !== null && brands.length === 0;
  const showFindDomainsButton =
    project?.selected_brand && domains !== null && domains.length === 0;
  // ---- Section stamps (Day 7) --------------------------------------
  const brandStamp = project?.selected_brand
    ? { status: "done", label: "Stamped" }
    : brandGenTask.state === "LOADING"
    ? { status: "loading", label: "Stamping…" }
    : brandGenTask.state === "ERROR"
    ? { status: "error", label: "Rejected" }
    : { status: "pending", label: "Pending" };
  const domainStamp = project?.selected_domain
    ? { status: "done", label: "Stamped" }
    : domainSearchTask.state === "LOADING"
    ? { status: "loading", label: "Stamping…" }
    : domainSearchTask.state === "ERROR"
    ? { status: "error", label: "Rejected" }
    : { status: "pending", label: "Pending" };
  const latestChecks = checks ? latestChecksByType(checks) : [];
  const readinessComplete =
    checks &&
    AVAILABLE_CHECK_TYPES.every(
      (type) => latestChecks.find((c) => c.check_type === type)?.status === "PASS"
    );
  const readinessFailed = checks && latestChecks.some((c) => c.status === "FAIL");
  const readinessStamp = readinessComplete
    ? { status: "done", label: "Stamped" }
    : dnsCheckTask.state === "LOADING"
    ? { status: "loading", label: "Stamping…" }
    : readinessFailed
    ? { status: "error", label: "Rejected" }
    : { status: "pending", label: "Pending" };
  const allReady =
    brandStamp.status === "done" && domainStamp.status === "done" && readinessStamp.status === "done";
  return (
    <div className="mx-auto my-12 max-w-xl p-4">
      <Link
        to="/dashboard"
        className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
      >
        ← Back to Dashboard
      </Link>
      <ErrorBanner error={error} />
      {!project && !error && <p className="mt-6 font-mono text-sm text-ink/40">Loading manifest…</p>}
      {project && (
        <div className="mt-4 overflow-hidden rounded-sm border-2 border-hairline bg-white shadow-sm">
          <div className="flex items-center justify-between border-b-2 border-hairline px-6 py-4">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">
                Domain Launch Assistant
              </p>
              <h1 className="font-display text-lg font-bold">{project.name}</h1>
            </div>
            <span className="rounded-sm border border-hairline px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
              {project.status}
            </span>
          </div>
          <div className="px-6 py-5">
            <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">Your business</p>
            <p className="mt-1 text-sm text-ink/80">{project.business_description}</p>
          </div>
          {/* 01 — BRAND */}
          <div className="px-6 pb-5">
            <div className="flex items-center justify-between">
              <p className="font-display text-sm font-bold uppercase tracking-wide">
                <span className="text-ink/30">01</span> Brand
              </p>
              <StampBadge status={brandStamp.status} label={brandStamp.label} />
            </div>
            {project.selected_brand && (
              <p className="mt-2 font-mono text-xl font-medium">{project.selected_brand.name}</p>
            )}
            {showGenerateButton && (
              <button
                onClick={handleGenerate}
                disabled={brandGenTask.state === "LOADING"}
                className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
              >
                {brandGenTask.state === "LOADING" ? "Generating…" : "Generate Brand Ideas"}
              </button>
            )}
            {brands && brands.length > 0 && !project.selected_brand && (
              <>
                <ul className="mt-3 space-y-2">
                  {brands.map((b) => (
                    <li
                      key={b.id}
                      className="flex items-center justify-between rounded-sm border border-hairline p-3"
                    >
                      <div>
                        <div className="font-display text-sm font-bold">{b.name}</div>
                        <div className="mt-0.5 text-xs text-ink/50">{b.description}</div>
                      </div>
                      <button
                        onClick={() => handleSelect(b.id)}
                        disabled={selectingId === b.id}
                        className="ml-3 shrink-0 rounded-sm border border-wire px-3 py-1 font-mono text-xs uppercase text-wire disabled:opacity-50"
                      >
                        {selectingId === b.id ? "Selecting…" : "Select"}
                      </button>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={handleGenerate}
                  disabled={brandGenTask.state === "LOADING"}
                  className="mt-3 font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink disabled:opacity-50"
                >
                  {brandGenTask.state === "LOADING" ? "Regenerating…" : "Not loving these? Regenerate"}
                </button>
              </>
            )}
          </div>
          <PerforatedDivider />
          {/* 02 — DOMAIN */}
          <div className="px-6 py-5">
            <div className="flex items-center justify-between">
              <p className="font-display text-sm font-bold uppercase tracking-wide">
                <span className="text-ink/30">02</span> Domain
              </p>
              <StampBadge status={domainStamp.status} label={domainStamp.label} />
            </div>
            {project.selected_domain && (
              <div className="mt-2">
                <p className="font-mono text-2xl font-medium tracking-tight">
                  {project.selected_domain.domain}
                </p>
                <div className="mt-2 flex gap-[2px]" aria-hidden="true">
                  {[...project.selected_domain.domain].map((ch, i) => (
                    <span
                      key={i}
                      className="bg-ink/70"
                      style={{ width: (ch.charCodeAt(0) % 3) + 1, height: 20 }}
                    />
                  ))}
                </div>
              </div>
            )}
            {showFindDomainsButton && (
              <button
                onClick={handleFindDomains}
                disabled={domainSearchTask.state === "LOADING"}
                className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
              >
                {domainSearchTask.state === "LOADING" ? "Searching…" : "Find Domains"}
              </button>
            )}
            {domains && domains.length > 0 && !project.selected_domain && (
              <>
                <ul className="mt-3 space-y-2">
                  {domains.map((d) => {
                    const rowStatus =
                      d.status === "AVAILABLE" ? "done" : d.status === "TAKEN" ? "pending" : "hold";
                    const isClaimed = claimedDomainIds.has(d.id);
                    return (
                      <li
                        key={d.id}
                        className="rounded-sm border border-hairline p-3"
                      >
                        <div className="flex items-center justify-between">
                          <div className="font-mono text-sm">{d.domain}</div>
                          <div className="flex items-center gap-2">
                            {d.status === "AVAILABLE" && d.purchase_price && (
                              <span className="font-mono text-xs text-ink/60">
                                ${d.purchase_price}/yr
                              </span>
                            )}
                            {d.premium && <StampBadge status="hold" label="Premium" />}
                            <StampBadge status={rowStatus} label={d.status} />
                            {d.status === "AVAILABLE" && !isClaimed && (
                              <button
                                onClick={() => handleSelectDomain(d.id)}
                                disabled={selectingDomainId === d.id}
                                className="rounded-sm border border-wire px-3 py-1 font-mono text-xs uppercase text-wire disabled:opacity-50"
                              >
                                {selectingDomainId === d.id ? "…" : "Select"}
                              </button>
                            )}
                          </div>
                        </div>
                        {d.status === "AVAILABLE" && (
                          <DomainClaimsCheck domainId={d.id} onChecked={handleClaimsChecked} />
                        )}
                      </li>
                    );
                  })}
                </ul>
                <button
                  onClick={handleFindDomains}
                  disabled={domainSearchTask.state === "LOADING"}
                  className="mt-3 font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink disabled:opacity-50"
                >
                  {domainSearchTask.state === "LOADING" ? "Regenerating…" : "Not loving these? Regenerate"}
                </button>
                <DomainRecommendationPanel projectId={id} triggerKey={searchVersion} />
              </>
            )}
          </div>
          <PerforatedDivider />
          {/* 03 — READINESS */}
          {project.selected_domain && (
            <div className="px-6 py-5">
              <div className="flex items-center justify-between">
                <p className="font-display text-sm font-bold uppercase tracking-wide">
                  <span className="text-ink/30">03</span> Readiness
                </p>
                <StampBadge status={readinessStamp.status} label={readinessStamp.label} />
              </div>
              <button
                onClick={handleRunChecks}
                disabled={dnsCheckTask.state === "LOADING"}
                className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
              >
                {dnsCheckTask.state === "LOADING" ? "Running…" : "Run Checks"}
              </button>
              {checks && checks.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {latestChecks.map((c) => {
                    const rowStatus =
                      c.status === "PASS"
                        ? "done"
                        : c.status === "FAIL"
                        ? "error"
                        : c.status === "ERROR"
                        ? "hold"
                        : "pending";
                    return (
                      <li key={c.id} className="rounded-sm border border-hairline p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-sm">{c.check_type}</span>
                          <StampBadge status={rowStatus} label={c.status} />
                        </div>
                        {c.message && <p className="mt-1 text-xs text-ink/50">{c.message}</p>}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
          {/* 04 — CHECKOUT (Day 3, Feature 6) */}
          {project.status === "READY" && project.selected_domain && (
            <>
              <PerforatedDivider />
              <DomainCheckoutPanel domain={project.selected_domain} />
            </>
          )}
          <PerforatedDivider />
          {/* FINAL SEAL */}
          <div className="px-6 pb-6 pt-2 text-center">
            <StampBadge
              status={allReady ? "done" : "pending"}
              label={allReady ? "Ready to Launch" : "In Progress"}
            />
          </div>
        </div>
      )}
    </div>
  );
}