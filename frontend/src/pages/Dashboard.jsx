import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { listProjects } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";
import Mascot from "../components/Mascot";
import StampBadge from "../components/StampBadge";

// Left-edge status strip per project row — lets the whole list be
// scanned by color without reading each status pill individually.
const STATUS_STRIP = {
  READY: "border-l-live",
  DRAFT: "border-l-hairline",
};

function statusStripClass(status) {
  return STATUS_STRIP[status] ?? "border-l-hold";
}

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
    <div className="min-h-screen bg-paper">
      <div className="mx-auto max-w-2xl p-6">
        <div className="mb-8 flex items-center justify-between">
          <Logo size="md" />
          <button
            onClick={logout}
            className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
          >
            Log out
          </button>
        </div>

        <h1 className="mb-6 font-display text-2xl font-bold text-ink">
          Welcome{user?.first_name ? `, ${user.first_name}` : ""}
        </h1>

        <Link
          to="/projects/new"
          className="mb-6 inline-block rounded-sm bg-signal px-5 py-2.5 font-display text-sm font-bold uppercase tracking-wide text-white transition hover:bg-signal/90"
        >
          + New Manifest
        </Link>

        <ErrorBanner error={error} />

        {projects === null && !error && (
          <div className="flex items-center gap-2">
            <StampBadge status="loading" label="Loading manifests" />
          </div>
        )}

        {projects?.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-sm border-2 border-dashed border-hairline py-10 text-center">
            <Mascot pose="idle" size={56} />
            <p className="font-mono text-sm text-ink/40">
              No manifests filed yet — create your first one.
            </p>
          </div>
        )}

        <ul className="space-y-3">
          {projects?.map((p) => (
            <li key={p.id}>
              <Link
                to={`/projects/${p.id}`}
                className={
                  "flex items-center justify-between rounded-sm border-2 border-l-4 border-hairline bg-surface p-4 transition hover:border-signal/50 " +
                  statusStripClass(p.status)
                }
              >
                <div className="font-display font-bold text-ink">{p.name}</div>
                <span className="rounded-sm border border-hairline px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
                  {p.status}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}