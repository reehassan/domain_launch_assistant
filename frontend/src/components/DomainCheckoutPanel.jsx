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
import { useEffect } from "react";
import { simulateRegistration } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import StampBadge from "./StampBadge";
import ErrorBanner from "./ErrorBanner";

export default function DomainCheckoutPanel({ domain, onRegistered }) {
  const checkoutTask = useTaskPolling();

  async function handleCheckout() {
    await checkoutTask.run(() => simulateRegistration(domain.id));
  }

  const isLoading = checkoutTask.state === "LOADING";
  // task.result on SUCCESS: { simulated: true, order_id, message }
  const receipt = checkoutTask.state === "SUCCESS" ? checkoutTask.result : null;

  useEffect(() => {
    if (receipt && onRegistered) {
      onRegistered(receipt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [receipt]);

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

      {checkoutTask.state === "ERROR" && checkoutTask.error && (
        <ErrorBanner error={checkoutTask.error} />
      )}
    </div>
  );
}