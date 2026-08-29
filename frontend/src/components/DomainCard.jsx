// frontend/src/components/DomainCard.jsx
//
// One domain result, rendered as a grid card rather than a row in a
// flat list. Domain selection is a "pick one of several comparable
// options" interaction, not a checklist — the layout should say that.
//
// Owns no async state itself (selection is still driven by the
// parent; the trademark check is driven by DomainClaimsCheck, which
// now runs automatically rather than needing a click — Ticket 6).
//
// claimStatus is one of "CHECKING" | "CLEAR" | "CLAIMED" | "ERROR" |
// undefined (before DomainClaimsCheck's mount effect has reported in
// yet), supplied by the parent via DomainClaimsCheck's onChecked
// callback. "Select" only renders once claimStatus === "CLEAR" — this
// is what actually closes the gap the ticket describes: previously
// "Select" was available the instant results loaded, with no
// relationship at all to whether a claims check had ever run.
import DomainClaimsCheck from "./DomainClaimsCheck";
import StampBadge from "./StampBadge";

export default function DomainCard({ domain: d, claimStatus, selecting, onSelect, onChecked }) {
  const rowStatus = d.status === "AVAILABLE" ? "done" : d.status === "TAKEN" ? "pending" : "hold";
  const isAvailable = d.status === "AVAILABLE";
  const isClaimed = claimStatus === "CLAIMED";
  const canSelect = isAvailable && claimStatus === "CLEAR";

  return (
    <div
      className={
        "flex flex-col justify-between rounded-sm border-2 p-3 transition " +
        (canSelect ? "border-hairline hover:border-wire/60" : "border-hairline opacity-70")
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
      {canSelect && (
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