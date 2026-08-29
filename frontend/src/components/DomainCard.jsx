// frontend/src/components/DomainCard.jsx
//
// One domain result, rendered as a grid card rather than a row in a
// flat list. Domain selection is a "pick one of several comparable
// options" interaction, not a checklist — the layout should say that.
//
// Owns no async state itself (selection and the trademark check are
// still driven by the parent / DomainClaimsCheck respectively) — this
// component is purely presentational, which keeps it easy to reuse in
// a grid, a carousel, or a single-column list on mobile without any
// logic changes.

import DomainClaimsCheck from "./DomainClaimsCheck";
import StampBadge from "./StampBadge";

export default function DomainCard({ domain: d, isClaimed, selecting, onSelect, onChecked }) {
  const rowStatus = d.status === "AVAILABLE" ? "done" : d.status === "TAKEN" ? "pending" : "hold";
  const isAvailable = d.status === "AVAILABLE";

  return (
    <div
      className={
        "flex flex-col justify-between rounded-sm border-2 p-3 transition " +
        (isAvailable && !isClaimed ? "border-hairline hover:border-wire/60" : "border-hairline opacity-70")
      }
    >
      <div>
        <div className="flex items-start justify-between gap-2">
          <p className="break-all font-mono text-sm font-medium">{d.domain}</p>
          {d.premium && <StampBadge status="hold" label="Premium" />}
        </div>

        <div className="mt-2 flex items-center justify-between">
          <StampBadge status={rowStatus} label={d.status} />
          {isAvailable && d.purchase_price && (
            <span className="font-mono text-xs text-ink/60">${d.purchase_price}/yr</span>
          )}
        </div>

        {isAvailable && <DomainClaimsCheck domainId={d.id} onChecked={onChecked} />}

        {isClaimed && (
          <p className="mt-2 font-mono text-[11px] text-reject">
            Has trademark claims — pick a different domain.
          </p>
        )}
      </div>

      {isAvailable && !isClaimed && (
        <button
          onClick={() => onSelect(d.id)}
          disabled={selecting}
          className="mt-3 w-full rounded-sm border border-wire px-3 py-1.5 font-mono text-xs uppercase text-wire transition hover:bg-wire/10 disabled:opacity-50"
        >
          {selecting ? "Selecting…" : "Select this domain"}
        </button>
      )}
    </div>
  );
}
