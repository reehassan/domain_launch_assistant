// frontend/src/components/DomainClaimsCheck.jsx
//
// Self-contained "trademark claims" checker for a single AVAILABLE
// domain result. Runs automatically as soon as it mounts (Ticket 6 —
// the check used to be an optional manual click, which meant a
// founder could select a domain without it ever running; the fix
// makes it non-optional by kicking off the check the moment the card
// appears, instead of waiting for a click).
//
// Owns its own useTaskPolling() instance so multiple rows can each
// have an in-flight check without clobbering each other's state — see
// ProjectDetails.jsx for why this isn't a single shared task instance.
//
// Reports its status back up via onChecked(domainId, status), where
// status is one of "CHECKING" | "CLEAR" | "CLAIMED" | "ERROR" — the
// parent (DomainStep/DomainCard) uses this to withhold the "Select"
// action until the check has actually resolved to CLEAR, closing the
// race where Select could otherwise render before the check completes.
//
// claims_data shape (name.com's Check Domain Claims response — see
// docs.name.com/api/v1/reference/domain-info/check-domain-claims):
//   { domain, claims: [TrademarkClaim, ...], claimsProcessActive,
//     claimId, notBefore, notAfter, claimsNotice }
// The claimId/notBefore/notAfter that identify the claim itself are
// top-level fields, not per-entry — each item in `claims` (when present)
// is a TrademarkClaim: {trademark, holder, jurisdiction, ...}.
import { useEffect } from "react";
import { checkDomainClaims } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import StampBadge from "./StampBadge";

export default function DomainClaimsCheck({ domainId, onChecked }) {
  const claimsTask = useTaskPolling();

  // Kick off the check the moment this domain's card mounts — no
  // click required. DomainCard only mounts this for AVAILABLE
  // results, so every selectable domain gets checked automatically.
  useEffect(() => {
    claimsTask.run(() => checkDomainClaims(domainId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId]);

  useEffect(() => {
    if (!onChecked) return;
    if (claimsTask.state === "SUCCESS" && claimsTask.result) {
      onChecked(domainId, claimsTask.result.has_claims ? "CLAIMED" : "CLEAR");
    } else if (claimsTask.state === "ERROR") {
      onChecked(domainId, "ERROR");
    } else if (claimsTask.state === "LOADING") {
      onChecked(domainId, "CHECKING");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claimsTask.state, claimsTask.result]);

  if (claimsTask.state === "SUCCESS" && claimsTask.result) {
    const claim = claimsTask.result;
    const data = claim.claims_data ?? {};
    const trademarkEntries = data.claims ?? [];
    return (
      <div className="mt-2 rounded-sm border border-hairline p-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-ink/60">Trademark claims</span>
          <StampBadge
            status={claim.has_claims ? "error" : "done"}
            label={claim.has_claims ? "Has Claims" : "No Claims"}
          />
        </div>
        {claim.has_claims && (
          <>
            <p className="mt-1 font-mono text-[11px] text-reject">
              This domain has trademark claims — choose a different one below.
            </p>
            <p className="mt-1 font-mono text-[11px] text-ink/50">
              Claim {data.claimId} — valid {data.notBefore} to {data.notAfter}
            </p>
          </>
        )}
        {trademarkEntries.length > 0 && (
          <ul className="mt-1 space-y-1 font-mono text-[11px] text-ink/50">
            {trademarkEntries.map((entry, i) => (
              <li key={entry.registrationNumber ?? i}>
                {entry.trademark} — held by {entry.holder}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  if (claimsTask.state === "ERROR") {
    return (
      <div className="mt-2">
        <p className="font-mono text-[11px] text-reject">
          {claimsTask.error?.message ?? "Trademark check failed."}
        </p>
        <button
          onClick={() => claimsTask.run(() => checkDomainClaims(domainId))}
          className="mt-1 rounded-sm border border-wire px-3 py-1 font-mono text-xs uppercase text-wire"
        >
          Retry check
        </button>
      </div>
    );
  }

  // IDLE (briefly, before the mount effect fires) or LOADING — the
  // check is automatic now, so this is just a status line, not a
  // call-to-action button anymore.

  return (
  <div className="mt-2">
    <StampBadge status="loading" label="Checking claims" />
  </div>
);
}