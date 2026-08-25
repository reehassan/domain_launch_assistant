// frontend/src/utils/checks.js

// Dedupe a DomainCheck list down to the latest run per check_type.
// Backend preserves full check history on purpose — DomainCheck.domain_result
// uses PROTECT specifically to keep old rows when checks are re-run (see
// dns/models.py) — so a second "Run Checks" click appends new rows rather
// than overwriting the previous run's results for the same check_type.
// checks/ already comes back ordered by -checked_at (dns/views.py), so the
// first row seen per check_type is the most recent one.
export function latestChecksByType(checks) {
  const seen = new Map();
  for (const c of checks) {
    if (!seen.has(c.check_type)) seen.set(c.check_type, c);
  }
  return Array.from(seen.values());
}