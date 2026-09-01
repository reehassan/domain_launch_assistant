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
// Edit/Delete: name.com's UpdateRecord is a full replace, not a patch
// (see namecom.py's update_record docstring), so clicking Edit seeds
// the same create/update form with the record's current values rather
// than opening a separate partial-field editor — submitting always
// sends the complete desired record either way. One shared
// useTaskPolling() instance (actionTask) covers create/update/delete,
// consistent with the backend only ever allowing one in-flight task
// per project at a time (TaskRecord.has_active_task) — there's never
// a moment where two of these three actions are legitimately
// concurrent for the same domain.
//
// Owns its own useTaskPolling() instance, same reasoning as every
// other panel in this app: its in-flight request shouldn't be tangled
// with any other section's loading state.
import { useEffect, useState } from "react";
import { listDnsRecords, createDnsRecord, updateDnsRecord, deleteDnsRecord } from "../api/dns";
import { useTaskPolling } from "../hooks/useTaskPolling";
import { parseApiError } from "../api/client";
import StampBadge from "./StampBadge";
import ErrorBanner from "./ErrorBanner";

const EMPTY_FORM = { host: "", type: "A", answer: "" };

export default function DomainDnsPanel({ domain }) {
  const [records, setRecords] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingRecordId, setEditingRecordId] = useState(null);
  const [deletingRecordId, setDeletingRecordId] = useState(null);
  const actionTask = useTaskPolling();

  useEffect(() => {
    let mounted = true;
    listDnsRecords(domain.id)
      .then((data) => mounted && setRecords(data))
      .catch((err) => mounted && setLoadError(parseApiError(err)));
    return () => {
      mounted = false;
      actionTask.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain.id]);

  useEffect(() => {
    if (actionTask.state !== "SUCCESS") return;
    if (deletingRecordId !== null) {
      setRecords((prev) => (prev ?? []).filter((r) => r.id !== deletingRecordId));
      setDeletingRecordId(null);
    } else if (editingRecordId !== null && actionTask.result) {
      setRecords((prev) =>
        (prev ?? []).map((r) => (r.id === editingRecordId ? actionTask.result : r))
      );
      setEditingRecordId(null);
      setForm(EMPTY_FORM);
    } else if (actionTask.result) {
      setRecords((prev) => [...(prev ?? []), actionTask.result]);
      setForm(EMPTY_FORM);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionTask.state, actionTask.result]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (editingRecordId !== null) {
      await actionTask.run(() =>
        updateDnsRecord(domain.id, editingRecordId, {
          host: form.host,
          type: form.type,
          answer: form.answer,
          ttl: 300,
        })
      );
    } else {
      await actionTask.run(() =>
        createDnsRecord(domain.id, {
          host: form.host,
          type: form.type,
          answer: form.answer,
          ttl: 300,
        })
      );
    }
  }

  function handleEditClick(record) {
    setEditingRecordId(record.id);
    setForm({ host: record.host || "", type: record.type, answer: record.answer });
  }

  function handleCancelEdit() {
    setEditingRecordId(null);
    setForm(EMPTY_FORM);
  }

  async function handleDelete(recordId) {
    setDeletingRecordId(recordId);
    await actionTask.run(() => deleteDnsRecord(domain.id, recordId));
  }

  const isLoading = actionTask.state === "LOADING";

  return (
    <div className="px-6 py-5">
      <div className="flex items-center justify-between">
        <p className="font-display text-sm font-bold uppercase tracking-wide">
          <span className="text-ink/30">05</span> Point Your Domain
        </p>
      </div>
      <p className="mt-1 text-xs text-ink/60">
        Add a DNS record so {domain.domain} points somewhere. Runs against
        name.com&apos;s sandbox — no real DNS is affected.
      </p>
      {loadError && <ErrorBanner error={loadError} />}

      {records === null && !loadError && (
        <div className="mt-2">
          <StampBadge status="loading" label="Loading records" />
        </div>
      )}
      {records && records.length > 0 && (
        <ul className="mt-3 space-y-2">
          {records.map((r) => (
            <li
              key={r.id}
              className="flex flex-col gap-1 rounded-sm border border-hairline p-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs">
                  {r.host || "@"}.{domain.domain} → {r.answer}
                </span>
                <StampBadge status="done" label={r.type} />
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleEditClick(r)}
                  disabled={isLoading}
                  className="font-mono text-[10px] uppercase text-ink/40 underline decoration-dotted hover:text-ink disabled:opacity-50"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(r.id)}
                  disabled={isLoading}
                  className="font-mono text-[10px] uppercase text-reject/70 underline decoration-dotted hover:text-reject disabled:opacity-50"
                >
                  {deletingRecordId === r.id && isLoading ? "Removing…" : "Delete"}
                </button>
              </div>
            </li>
          ))}
        </ul>

      )}
      <form onSubmit={handleSubmit} className="mt-3 space-y-2">
        {editingRecordId !== null && (
          <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">
            Editing record — Update replaces it entirely
          </p>
        )}
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
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={isLoading || !form.answer}
            className="rounded-sm bg-signal px-4 py-2 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
          >
            {isLoading
              ? editingRecordId !== null
                ? "Updating…"
                : "Adding…"
              : editingRecordId !== null
              ? "Update DNS Record"
              : "Add DNS Record"}
          </button>
          {editingRecordId !== null && (
            <button
              type="button"
              onClick={handleCancelEdit}
              disabled={isLoading}
              className="font-mono text-xs uppercase text-ink/40 underline decoration-dotted hover:text-ink disabled:opacity-50"
            >
              Cancel
            </button>
          )}
        </div>
      </form>
      {actionTask.state === "ERROR" && actionTask.error && (
        <ErrorBanner error={actionTask.error} />
      )}
    </div>
  );
}