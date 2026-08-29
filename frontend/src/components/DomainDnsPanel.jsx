// frontend/src/components/DomainDnsPanel.jsx
//
// "05 — Point your domain" panel (Feature 7). The real fourth name.com
// integration in this app: unlike every other panel here, this one has
// no local model behind it at all — name.com's DNS Records API is the
// only source of truth, so listDnsRecords() is a live proxy read every
// time this mounts, not a cache.
//
// Runs against name.com's SANDBOX only (see dns/services/dns_records.py)
// — the domain only exists there, since registration itself is
// sandbox-simulated. Nothing about "was this domain actually
// registered" is tracked server-side by design (registration_simulation.py
// persists nothing), so this panel's visibility is a same-session UI
// gate — rendered by LaunchStep only after a checkout receipt exists
// this session — not a backend-enforced one. That's consistent with
// the same limitation checkout itself already accepts, not a new one.
//
// Restricts the record type dropdown to A / CNAME — the two types a
// founder pointing a domain at something actually needs day one. Same
// frontend-only narrowing convention as AVAILABLE_CHECK_TYPES in
// api/dns.js: name.com and the backend both support the full type
// enum (A, AAAA, ANAME, CNAME, MX, NS, SRV, TXT); this is a UI choice,
// not a backend limitation.
//
// Owns its own useTaskPolling() instance for the create action, same
// reasoning as every other panel in this app: its in-flight request
// shouldn't be tangled with any other section's loading state.

import { useEffect, useState } from "react";
import { listDnsRecords, createDnsRecord } from "../api/dns";
import { useTaskPolling } from "../hooks/useTaskPolling";
import { parseApiError } from "../api/client";
import StampBadge from "./StampBadge";
import ErrorBanner from "./ErrorBanner";

export default function DomainDnsPanel({ domain }) {
  const [records, setRecords] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState({ host: "", type: "A", answer: "" });
  const createTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    listDnsRecords(domain.id)
      .then((data) => mounted && setRecords(data))
      .catch((err) => mounted && setLoadError(parseApiError(err)));
    return () => {
      mounted = false;
      createTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain.id]);

  useEffect(() => {
    if (createTask.state === "SUCCESS" && createTask.result) {
      setRecords((prev) => [...(prev ?? []), createTask.result]);
      setForm({ host: "", type: "A", answer: "" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createTask.state, createTask.result]);

  async function handleSubmit(e) {
    e.preventDefault();
    await createTask.run(() =>
      createDnsRecord(domain.id, {
        host: form.host,
        type: form.type,
        answer: form.answer,
        ttl: 300,
      })
    );
  }

  const isLoading = createTask.state === "LOADING";

  return (
    <div className="px-6 py-5">
      <div className="flex items-center justify-between">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">05</span> Point Your Domain
        </p>
      </div>

      <p className="mt-1 text-xs text-ink/60">
        Add a DNS record so {domain.domain} points somewhere. Runs against
        name.com's sandbox — no real DNS is affected.
      </p>

      {loadError && <ErrorBanner error={loadError} />}

      {records === null && !loadError && (
        <p className="mt-2 font-mono text-xs text-ink/40">Loading records…</p>
      )}

      {records && records.length > 0 && (
        <ul className="mt-3 space-y-2">
          {records.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between rounded-sm border border-hairline p-2"
            >
              <span className="font-mono text-xs">
                {r.host || "@"}.{domain.domain} → {r.answer}
              </span>
              <StampBadge status="done" label={r.type} />
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="mt-3 space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <input
            className="rounded-sm border border-hairline bg-paper px-2 py-1.5 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
            placeholder="Host (blank = @)"
            value={form.host}
            onChange={(e) => setForm({ ...form, host: e.target.value })}
          />
          <select
            className="rounded-sm border border-hairline bg-paper px-2 py-1.5 text-sm text-ink outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
            value={form.type}
            onChange={(e) => setForm({ ...form, type: e.target.value })}
          >
            <option value="A">A</option>
            <option value="CNAME">CNAME</option>
          </select>
          <input
            className="rounded-sm border border-hairline bg-paper px-2 py-1.5 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
            placeholder={form.type === "A" ? "IP address" : "Target hostname"}
            value={form.answer}
            onChange={(e) => setForm({ ...form, answer: e.target.value })}
            required
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !form.answer}
          className="rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
        >
          {isLoading ? "Adding…" : "Add DNS Record"}
        </button>
      </form>

      {createTask.state === "ERROR" && createTask.error && (
        <ErrorBanner error={createTask.error} />
      )}
    </div>
  );
}