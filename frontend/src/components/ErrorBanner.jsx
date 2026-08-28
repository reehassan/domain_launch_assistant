// src/components/ErrorBanner.jsx
// Reworked into the "REJECTED" stamp — errors read as a customs
// rejection, not a generic toast. Same {error} contract as before, so
// no caller needs to change.

export default function ErrorBanner({ error }) {
  if (!error) return null;

  const fieldErrors =
    error.details && typeof error.details === "object"
      ? Object.entries(error.details)
      : [];

  return (
    <div className="my-4 flex gap-3 rounded-sm border-2 border-dashed border-reject/40 bg-reject/5 p-4">
      <span className="inline-block h-fit shrink-0 -rotate-6 rounded-sm border-2 border-reject px-2 py-1 font-display text-xs font-bold uppercase tracking-wider text-reject">
        ✕ Rejected
      </span>
      <div className="text-sm">
        <p className="font-medium text-reject">{error.message}</p>
        {fieldErrors.length > 0 && (
          <ul className="mt-1 list-disc pl-5 text-ink/70">
            {fieldErrors.map(([field, msgs]) => (
              <li key={field}>
                <span className="font-mono text-xs">{field}</span>:{" "}
                {Array.isArray(msgs) ? msgs.join(" ") : String(msgs)}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
