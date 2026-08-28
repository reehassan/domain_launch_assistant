import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { listProjects } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState(null); // null = still loading
  const [error, setError] = useState(null);

  useEffect(() => {
    listProjects()
      .then(setProjects)
      .catch((err) => setError(parseApiError(err)));
  }, []);

  return (
    <div className="mx-auto max-w-2xl p-6">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-ink/40">
            Domain Launch Assistant
          </p>
          <h1 className="font-display text-2xl font-bold">
            Welcome{user?.first_name ? `, ${user.first_name}` : ""}
          </h1>
        </div>
        <button
          onClick={logout}
          className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
        >
          Log out
        </button>
      </div>

      <Link
        to="/projects/new"
        className="mb-6 inline-block rounded-sm bg-signal px-5 py-2.5 font-display text-sm font-bold uppercase tracking-wide text-white transition hover:bg-signal/90"
      >
        + New Manifest
      </Link>

      <ErrorBanner error={error} />

      {projects === null && !error && (
        <p className="font-mono text-sm text-ink/40">Loading manifests…</p>
      )}

      {projects?.length === 0 && (
        <p className="font-mono text-sm text-ink/40">
          No manifests filed yet — create your first one.
        </p>
      )}

      <ul className="space-y-3">
        {projects?.map((p) => (
          <li key={p.id}>
            <Link
              to={`/projects/${p.id}`}
              className="flex items-center justify-between rounded-sm border-2 border-hairline bg-white p-4 transition hover:border-ink"
            >
              <div className="font-display font-bold">{p.name}</div>
              <span className="rounded-sm border border-hairline px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
                {p.status}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
