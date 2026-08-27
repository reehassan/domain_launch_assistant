// frontend/src/components/DomainClaimsCheck.jsx
//
// Self-contained "Check for trademark claims" widget for a single
// AVAILABLE domain result. Owns its own useTaskPolling() instance so
// multiple rows can each have an in-flight check without clobbering
// each other's state — see ProjectDetails.jsx for why this isn't a
// single shared task instance.
//
// Reports has_claims back up via onChecked(domainId, hasClaims) so the
// parent row can disable "Select" on a claimed domain and steer the
// founder toward picking a different one instead.
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

  async function handleCheck() {
    await claimsTask.run(() => checkDomainClaims(domainId));
  }

  useEffect(() => {
    if (claimsTask.state === "SUCCESS" && claimsTask.result && onChecked) {
      onChecked(domainId, claimsTask.result.has_claims);
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

  return (
    <div className="mt-2">
      <button
        onClick={handleCheck}
        disabled={claimsTask.state === "LOADING"}
        className="rounded-sm border border-wire px-3 py-1 font-mono text-xs uppercase text-wire disabled:opacity-50"
      >
        {claimsTask.state === "LOADING" ? "Checking…" : "Check for Trademark Claims"}
      </button>
      {claimsTask.state === "ERROR" && claimsTask.error && (
        <p className="mt-1 font-mono text-[11px] text-reject">{claimsTask.error.message}</p>
      )}
    </div>
  );
}