// frontend/src/components/DomainCheckoutPanel.jsx
//
// Feature 6 — on-platform cart/checkout (Day 3 revision from a plain
// "buy on name.com" link). Calls the existing sandbox-only
// POST /domains/{id}/simulate-registration/ endpoint — no real payment,
// no real name.com purchase.
//
// Persistence fix (post-Ticket 15): registered/privacy state used to
// live ONLY in this component's local useTaskPolling result — which
// meant navigating away (e.g. to the Launch Report page) and back, or
// a plain reload, made a genuinely-registered domain look unregistered
// again, since the local state was gone but the sandbox registration
// itself was still real on name.com's side. Now the backend persists
// registered_at/registration_order_id/privacy_enabled onto DomainResult
// (see domains/tasks.py), so `domain` (project.selected_domain) already
// carries the true last-known state on every fresh mount — this
// component seeds its display from those fields first, and only falls
// back to the local task result for what just happened THIS session
// (e.g. a fresh order_id/message from a checkout click just now).
//
// Owns its own useTaskPolling() instances so this panel's in-flight
// requests don't tangle with any other section's loading state.
//
// onRegistered fires once a) immediately on mount if the domain was
// already registered (persisted), or b) when a fresh checkout in this
// session succeeds — LaunchStep uses it to know when to reveal
// DomainDnsPanel without waiting for a project refetch.
//
// onJustRegistered fires ONLY for case (b) above — a genuine
// registration completing THIS session, not the "already registered on
// mount" replay. LaunchStep uses this narrower signal to trigger the
// launch celebration exactly once, instead of re-celebrating every time
// someone revisits an already-registered project.
import { useEffect, useState } from "react";
import { simulateRegistration, togglePrivacy } from "../api/domains";
import { useTaskPolling } from "../hooks/useTaskPolling";
import StampBadge from "./StampBadge";
import ErrorBanner from "./ErrorBanner";

export default function DomainCheckoutPanel({ domain, onRegistered, onJustRegistered }) {
  const checkoutTask = useTaskPolling();
  const privacyTask = useTaskPolling();

  const alreadyRegistered = Boolean(domain.registered_at);
  // task.result on SUCCESS: { simulated: true, order_id, privacy_enabled, message }
  const freshReceipt = checkoutTask.state === "SUCCESS" ? checkoutTask.result : null;
  const isRegistered = alreadyRegistered || Boolean(freshReceipt);
  const orderId = freshReceipt?.order_id ?? domain.registration_order_id;
  const receiptMessage =
    freshReceipt?.message ??
    (alreadyRegistered
      ? "Registered in name.com sandbox — no real domain or charge."
      : null);

  const [privacyEnabled, setPrivacyEnabled] = useState(domain.privacy_enabled ?? null);
  const privacyDisplay = privacyEnabled ?? false;
  const isLoading = checkoutTask.state === "LOADING";
  const isTogglingPrivacy = privacyTask.state === "LOADING";
  const privacyResult = privacyTask.state === "SUCCESS" ? privacyTask.result : null;

  async function handleCheckout() {
    await checkoutTask.run(() => simulateRegistration(domain.id));
  }

  async function handleTogglePrivacy() {
    await privacyTask.run(() => togglePrivacy(domain.id, !privacyDisplay));
  }

  // Fires once on mount if already-registered (persisted state) — no
  // celebration here, this is just "the panel is catching up to reality".
  useEffect(() => {
    if (alreadyRegistered && onRegistered) {
      onRegistered({ order_id: domain.registration_order_id });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fires when a fresh checkout completes THIS session — this is the
  // genuine "just launched" moment.
  useEffect(() => {
    if (freshReceipt) {
      if (onRegistered) onRegistered(freshReceipt);
      if (onJustRegistered) onJustRegistered(freshReceipt);
      if (privacyEnabled === null) {
        setPrivacyEnabled(freshReceipt.privacy_enabled ?? false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [freshReceipt]);

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
        {isRegistered && <StampBadge status="done" label="Registered" />}
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
      {!isRegistered && (
        <button
          onClick={handleCheckout}
          disabled={isLoading}
          className="mt-3 rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
        >
          {isLoading ? "Registering…" : "Complete Purchase"}
        </button>
      )}
      {isRegistered && orderId && (
        <div className="mt-3 rounded-sm border border-live/40 bg-live/5 p-3">
          <p className="font-mono text-xs text-ink/60">Order ID</p>
          <p className="font-mono text-sm">{orderId}</p>
          {receiptMessage && <p className="mt-2 text-xs text-ink/70">{receiptMessage}</p>}
        </div>
      )}
      {isRegistered && (
        <div className="mt-3 flex items-center justify-between rounded-sm border border-hairline p-3">
          <div>
            <p className="font-mono text-xs text-ink/60">WHOIS Privacy</p>
            <p className="mt-0.5 text-xs text-ink/70">
              {privacyDisplay ? "Enabled — registrant details hidden" : "Disabled — registrant details public"}
            </p>
          </div>
          <button
            onClick={handleTogglePrivacy}
            disabled={isTogglingPrivacy}
            aria-pressed={privacyDisplay}
            className={`rounded-sm px-3 py-1.5 font-display text-xs font-bold uppercase tracking-wide transition disabled:opacity-50 ${
              privacyDisplay
                ? "bg-signal text-white hover:bg-signal/90"
                : "border border-hairline text-ink/70 hover:bg-hairline/20"
            }`}
          >
            {isTogglingPrivacy ? "Updating…" : privacyDisplay ? "On" : "Off"}
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