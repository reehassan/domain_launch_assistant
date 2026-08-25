// frontend/src/pages/ProjectDetails.jsx — full file, Day 6 async wiring

import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getProject } from "../api/projects";
import { generateBrands, listBrands, selectBrand } from "../api/brands";
import { startDomainSearch, listDomainResults, selectDomain } from "../api/domains";
import { runChecks, listChecks } from "../api/dns";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import { latestChecksByType } from "../utils/checks";
import { useTaskPolling } from "../hooks/useTaskPolling";

export default function ProjectDetails() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [brands, setBrands] = useState(null); // null = not fetched yet
  const [domains, setDomains] = useState(null); // null = not fetched yet
  const [checks, setChecks] = useState(null); // null = not fetched yet / no selected domain
  const [error, setError] = useState(null);
  const [selectingId, setSelectingId] = useState(null); // brand id currently being selected
  const [selectingDomainId, setSelectingDomainId] = useState(null);

  // Day 6: generate-brands/, domain-search/, and check/ are all async
  // now (202 + task_id). Each gets its own polling instance so the
  // three operations can run/show independently.
  const brandGenTask = useTaskPolling();
  const domainSearchTask = useTaskPolling();
  const dnsCheckTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;

    getProject(id)
      .then((p) => {
        if (!mounted) return;
        setProject(p);
        // Fetch brands and any existing domain results regardless of
        // status — lets a page refresh after selection still show
        // correct state, reading from the backend rather than local
        // state. Only fetch checks if a domain is already selected
        // (checks/ is scoped to a DomainResult.id).
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
      // Stop any in-flight polling loops if the page is left mid-task.
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
      // Update project status from the response directly — no refetch.
      setProject((prev) => ({ ...prev, status: result.status, selected_brand: result.selected_brand }));
      // Flip is_selected locally so the UI updates without a refetch.
      setBrands((prev) =>
        prev.map((b) => ({ ...b, is_selected: b.id === brandId }))
      );
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
      // Selecting a domain is what makes checks/ meaningful — reset so
      // the checks section can fetch against the newly selected domain
      // instead of showing stale/empty state from before selection.
      setChecks(null);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setSelectingDomainId(null);
    }
  }

  async function handleRunChecks() {
    setError(null);
    await dnsCheckTask.run(() => runChecks(project.selected_domain.id));
  }

  useEffect(() => {
    if (dnsCheckTask.state === "SUCCESS") {
      setChecks(dnsCheckTask.result.results);
    } else if (dnsCheckTask.state === "ERROR") {
      setError(dnsCheckTask.error);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dnsCheckTask.state, dnsCheckTask.result, dnsCheckTask.error]);

  const showGenerateButton =
    project?.status === "DRAFT" && brands !== null && brands.length === 0;

  const showFindDomainsButton =
    project?.selected_brand && domains !== null && domains.length === 0;

  return (
    <div className="mx-auto mt-12 max-w-lg p-6">
      <Link to="/dashboard" className="text-sm text-gray-500 underline">
        ← Back to Dashboard
      </Link>

      <ErrorBanner error={error} />

      {!project && !error && <p className="mt-4 text-gray-500">Loading…</p>}

      {project && (
        <div className="mt-4">
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <p className="mt-1 inline-block rounded bg-gray-100 px-2 py-1 text-sm">
            {project.status}
          </p>
          <p className="mt-4 text-gray-700">{project.business_description}</p>

          {showGenerateButton && (
            <button
              onClick={handleGenerate}
              disabled={brandGenTask.state === "LOADING"}
              className="mt-4 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
            >
              {brandGenTask.state === "LOADING" ? "Generating…" : "Generate Brand Ideas"}
            </button>
          )}

          {brands && brands.length > 0 && (
            <ul className="mt-4 space-y-2">
              {brands.map((b) => (
                <li
                  key={b.id}
                  className="rounded border p-3 flex items-center justify-between"
                >
                  <div>
                    <div className="font-medium">
                      {b.name}
                      {b.is_selected && (
                        <span className="ml-2 text-xs text-green-700">
                          (selected)
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-500">
                      {b.description}
                    </div>
                  </div>
                  {!b.is_selected && (
                    <button
                      onClick={() => handleSelect(b.id)}
                      disabled={selectingId === b.id}
                      className="ml-3 shrink-0 rounded border px-3 py-1 text-sm disabled:opacity-50"
                    >
                      {selectingId === b.id ? "Selecting…" : "Select"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}

          {showFindDomainsButton && (
            <button
              onClick={handleFindDomains}
              disabled={domainSearchTask.state === "LOADING"}
              className="mt-4 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
            >
              {domainSearchTask.state === "LOADING" ? "Searching…" : "Find Domains"}
            </button>
          )}

          {domains && domains.length > 0 && (
            <ul className="mt-4 space-y-2">
              {domains.map((d) => (
                <li
                  key={d.id}
                  className="rounded border p-3 flex items-center justify-between"
                >
                  <div>
                    <div className="font-medium">{d.domain}</div>
                    <div
                      className={
                        "text-sm " +
                        (d.status === "AVAILABLE"
                          ? "text-green-700"
                          : d.status === "TAKEN"
                          ? "text-gray-500"
                          : "text-amber-600")
                      }
                    >
                      {d.status}
                    </div>
                  </div>
                  {d.status === "AVAILABLE" &&
                    project.selected_domain?.id !== d.id && (
                      <button
                        onClick={() => handleSelectDomain(d.id)}
                        disabled={selectingDomainId === d.id}
                        className="ml-3 shrink-0 rounded border px-3 py-1 text-sm disabled:opacity-50"
                      >
                        {selectingDomainId === d.id ? "Selecting…" : "Select"}
                      </button>
                    )}
                  {project.selected_domain?.id === d.id && (
                    <span className="ml-3 shrink-0 text-xs text-green-700">
                      (selected)
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}

          {project.selected_domain && (
            <div className="mt-6 border-t pt-4">
              <h2 className="text-sm font-semibold text-gray-700">
                Launch Checks
              </h2>
              <p className="mt-1 text-sm text-gray-500">
                {project.selected_domain.domain}
              </p>

              <button
                onClick={handleRunChecks}
                disabled={dnsCheckTask.state === "LOADING"}
                className="mt-2 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
              >
                {dnsCheckTask.state === "LOADING" ? "Running…" : "Run Checks"}
              </button>

              {checks === null && dnsCheckTask.state !== "LOADING" && (
                <p className="mt-3 text-sm text-gray-500">Loading checks…</p>
              )}

              {checks && checks.length === 0 && (
                <p className="mt-3 text-sm text-gray-500">
                  No checks run yet.
                </p>
              )}

              {checks && checks.length > 0 && (
                <ul className="mt-4 space-y-2">
                  {latestChecksByType(checks).map((c) => (
                    <li key={c.id} className="rounded border p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{c.check_type}</span>
                        <span
                          className={
                            "text-sm " +
                            (c.status === "PASS"
                              ? "text-green-700"
                              : c.status === "FAIL"
                              ? "text-red-600"
                              : c.status === "ERROR"
                              ? "text-amber-600"
                              : "text-gray-500")
                          }
                        >
                          {c.status}
                        </span>
                      </div>
                      {c.message && (
                        <p className="mt-1 text-sm text-gray-500">
                          {c.message}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}