export default function ErrorBanner({ error }) {
  if (!error) return null;

  // error.details, when present, is DRF's raw field-error object, e.g.
  // { business_description: ["This field is required."] }. Show it if
  // it's there — it's usually more useful than the generic message.
  const fieldErrors =
    error.details && typeof error.details === "object"
      ? Object.entries(error.details)
      : [];

  return (
    <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">
      <p className="font-medium">{error.message}</p>
      {fieldErrors.length > 0 && (
        <ul className="mt-1 list-disc pl-5">
          {fieldErrors.map(([field, msgs]) => (
            <li key={field}>
              <span className="font-mono">{field}</span>:{" "}
              {Array.isArray(msgs) ? msgs.join(" ") : String(msgs)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
