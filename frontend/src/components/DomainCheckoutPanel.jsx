// frontend/src/components/DomainCheckoutPanel.jsx
//
// Feature 6 — on-platform cart/checkout (Day 3 revision from a plain
// "buy on name.com" link). Calls the existing sandbox-only
// POST /domains/{id}/simulate-registration/ endpoint — no real payment,
// no real name.com purchase. That endpoint's own service layer refuses
// to run against anything but the sandbox host regardless of what this
// component does (see registration_simulation.py's _guard_base_url), so
// there's no client-side safety burden here — only rendered when the
// project is already READY, matching the endpoint's own 409 gate.
//
// Owns its own useTaskPolling() instance, same reasoning as
// DomainClaimsCheck.jsx / DomainRecommendationPanel.jsx: this panel's
// in-flight request shouldn't be tangled with any other section's
// loading state.
//
// onRegistered (Feature 7) is an optional callback fired once with the
// receipt when checkout succeeds — LaunchStep uses it to know when to
// reveal DomainDnsPanel. Purely additive: any existing caller that
// doesn't pass it behaves exactly as before.
//
// Ticket 15 — WHOIS privacy toggle. Rendered only once a receipt
// exists (post-registration), same placement the ticket calls for.
// Owns a SEPARATE useTaskPolling() instance from checkoutTask, same
// isolation reasoning as above — toggling privacy shouldn't touch the
// checkout button's loading state or vice versa. Initial on/off state
// comes straight off the checkout receipt (simulate_registration's
// response already includes privacy_enabled at zero extra cost — see
// registration_simulation.py), then gets overwritten by whatever
// toggle-privacy/ itself returns after each toggle.
import { useEffect, useState } from "react";
import { simulateRegistration, togglePrivacy } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import StampBadge from "./StampBadge";
import ErrorBanner from "./ErrorBanner";

export default function DomainCheckoutPanel({ domain, onRegistered }) {
  const checkoutTask = useTaskPolling();
  const privacyTask = useTaskPolling();
  const [privacyEnabled, setPrivacyEnabled] = useState(null);

  async function handleCheckout() {
    await checkoutTask.run(() => simulateRegistration(domain.id));
  }

  async function handleTogglePrivacy() {
    await privacyTask.run(() => togglePrivacy(domain.id, !privacyEnabled));
  }

  const isLoading = checkoutTask.state === "LOADING";
  // task.result on SUCCESS: { simulated: true, order_id, privacy_enabled, message }
  const receipt = checkoutTask.state === "SUCCESS" ? checkoutTask.result : null;

  const isTogglingPrivacy = privacyTask.state === "LOADING";
  // task.result on SUCCESS: { domain, privacy_enabled, message }
  const privacyResult = privacyTask.state === "SUCCESS" ? privacyTask.result : null;

  useEffect(() => {
    if (receipt && onRegistered) {
      onRegistered(receipt);
    }
    // Seed the toggle's displayed state from the receipt the first
    // time checkout succeeds.
    if (receipt && privacyEnabled === null) {
      setPrivacyEnabled(receipt.privacy_enabled ?? false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [receipt]);

  useEffect(() => {
    if (privacyResult) {
      setPrivacyEnabled(privacyResult.privacy_enabled ?? privacyEnabled);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [privacyResult]);

  return (
    <div className="px-6 py-5">
      <div className="flex items-center justify-between">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">04</span> Checkout
        </p>
        {receipt && <StampBadge status="done" label="Registered" />}
      </div>

      <div className="mt-2 rounded-sm border border-hairline p-3">
        <p className="font-mono text-lg font-medium tracking-tight">{domain.domain}</p>
        {domain.purchase_price && (
          <p className="mt-1 text-xs text-ink/60">${domain.purchase_price}/yr</p>
        )}
        <p className="mt-1 font-mono text-[10px] uppercase tracking-widest text-ink/40">
          Sandbox demo — no real charge
        </p>
      </div>

      {!receipt && (
        <button
          onClick={handleCheckout}
          disabled={isLoading}
          className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
        >
          {isLoading ? "Registering…" : "Complete Purchase"}
        </button>
      )}

      {receipt && (
        <div className="mt-3 rounded-sm border border-live/40 bg-live/5 p-3">
          <p className="font-mono text-xs text-ink/60">Order ID</p>
          <p className="font-mono text-sm">{receipt.order_id}</p>
          <p className="mt-2 text-xs text-ink/70">{receipt.message}</p>
        </div>
      )}

      {receipt && privacyEnabled !== null && (
        <div className="mt-3 flex items-center justify-between rounded-sm border border-hairline p-3">
          <div>
            <p className="font-mono text-xs text-ink/60">WHOIS Privacy</p>
            <p className="mt-0.5 text-xs text-ink/70">
              {privacyEnabled ? "Enabled — registrant details hidden" : "Disabled — registrant details public"}
            </p>
          </div>
          <button
            onClick={handleTogglePrivacy}
            disabled={isTogglingPrivacy}
            aria-pressed={privacyEnabled}
            className={`rounded-sm px-3 py-1.5 font-display text-xs font-bold uppercase tracking-wide transition disabled:opacity-50 ${
              privacyEnabled
                ? "bg-signal text-white hover:bg-signal/90"
                : "border border-hairline text-ink/70 hover:bg-hairline/20"
            }`}
          >
            {isTogglingPrivacy ? "Updating…" : privacyEnabled ? "On" : "Off"}
          </button>
        </div>
      )}

      {checkoutTask.state === "ERROR" && checkoutTask.error && (
        <ErrorBanner error={checkoutTask.error} />
      )}
      {privacyTask.state === "ERROR" && privacyTask.error && (
        <ErrorBanner error={privacyTask.error} />
      )}
    </div>
  );
}