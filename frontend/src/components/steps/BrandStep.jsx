// frontend/src/components/steps/BrandStep.jsx
//
// Step 01 of the launch flow. Fully self-contained: fetches its own
// brand list, owns its own generate/regenerate task, and reports
// upward only when something the shell needs to know about changes
// (a brand gets selected -> project.selected_brand / status update).
//
// `changingBrand`: lets the founder swap their selected brand for a
// different one when they've navigated back to view this (already
// "done") step via StepRail. Only offered while !project.selected_domain
// — once a domain search/selection has happened downstream, changing
// the brand out from under it would leave stale domain/verify/launch
// data around with nothing to reconcile it, so re-selection is
// intentionally locked out past that point (matches BrandIdeaSelectView
// having no server-side guard against re-selection at all — this is a
// frontend-only policy, not a backend limitation).

import { useEffect, useState } from "react";
import { generateBrands, listBrands, selectBrand } from "../../api/brands";
import { parseApiError } from "../../api/client";
import { useTaskPolling } from "../../hooks/useTaskPolling";
import ErrorBanner from "../ErrorBanner";
import StampBadge from "../StampBadge";

export default function BrandStep({ project, onProjectUpdate }) {
  const [brands, setBrands] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [selectingId, setSelectingId] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [changingBrand, setChangingBrand] = useState(false);
  const brandGenTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    listBrands(project.id)
      .then((data) => mounted && setBrands(data))
      .catch((err) => mounted && setLoadError(parseApiError(err)));
    return () => {
      mounted = false;
      brandGenTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  useEffect(() => {
    if (brandGenTask.state === "SUCCESS") {
      setBrands(brandGenTask.result);
    }
  }, [brandGenTask.state, brandGenTask.result]);

  // If we navigate away and back with a different project (or the
  // project's own selection changes under us), don't leave a stale
  // "changing" UI stuck open.
  useEffect(() => {
    setChangingBrand(false);
  }, [project.id, project.selected_brand?.id]);

  async function handleGenerate() {
    setActionError(null);
    await brandGenTask.run(() => generateBrands(project.id));
  }

  async function handleSelect(brandId) {
    setActionError(null);
    setSelectingId(brandId);
    try {
      const result = await selectBrand(project.id, brandId);
      setChangingBrand(false);
      onProjectUpdate({ status: result.status, selected_brand: result.selected_brand });
    } catch (err) {
      setActionError(parseApiError(err));
    } finally {
      setSelectingId(null);
    }
  }

  const canChangeBrand = Boolean(project.selected_brand) && !project.selected_domain;
  const showSelectedCard = Boolean(project.selected_brand) && !changingBrand;
  const showPickGrid = brands && brands.length > 0 && (!project.selected_brand || changingBrand);
  const showGenerateButton = brands !== null && brands.length === 0;

  return (
    <div>
      <ErrorBanner error={loadError} />
      <ErrorBanner error={actionError || (brandGenTask.state === "ERROR" ? brandGenTask.error : null)} />

      {showSelectedCard && (
        <div className="rounded-sm border-2 border-live/40 bg-live/5 p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-widest text-live">Selected brand</p>
              <p className="mt-1 font-display text-xl font-bold">{project.selected_brand.name}</p>
              {project.selected_brand.description && (
                <p className="mt-1 text-xs text-ink/60">{project.selected_brand.description}</p>
              )}
            </div>
            {canChangeBrand && (
              <button
                type="button"
                onClick={() => setChangingBrand(true)}
                className="shrink-0 font-mono text-[10px] uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
              >
                Change brand
              </button>
            )}
          </div>
        </div>
      )}

      {brands === null && !loadError && (
        <StampBadge status="loading" label="Loading brand ideas" />
      )}

      {showGenerateButton && (
        <button
          onClick={handleGenerate}
          disabled={brandGenTask.state === "LOADING"}
          className="rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
        >
          {brandGenTask.state === "LOADING" ? "Generating…" : "Generate Brand Ideas"}
        </button>
      )}

      {showPickGrid && (
        <>
          {changingBrand && (
            <button
              type="button"
              onClick={() => setChangingBrand(false)}
              className="mb-2 font-mono text-[10px] uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
            >
              ← Keep current brand
            </button>
          )}
          <p className="mb-2 font-mono text-[10px] uppercase tracking-widest text-ink/40">
            Pick one to move forward with
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {brands.map((b, i) => (
              <div
                key={b.id}
                className={
                  "flex flex-col justify-between rounded-sm border-2 p-3 " +
                  (i === 0 ? "border-wire/40 bg-elevated" : "border-hairline")
                }
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-display text-sm font-bold">{b.name}</div>
                    {i === 0 && (
                      <span className="shrink-0 font-mono text-[10px] uppercase tracking-wider text-wire">
                        ✦ Top pick
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-ink/50">{b.description}</div>
                </div>
                <button
                  onClick={() => handleSelect(b.id)}
                  disabled={selectingId === b.id}
                  className="mt-3 self-start rounded-sm border border-wire px-3 py-1 font-mono text-xs uppercase text-wire disabled:opacity-50"
                >
                  {selectingId === b.id ? "Selecting…" : "Select"}
                </button>
              </div>
            ))}
          </div>

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
  );
}