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
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          Welcome{user?.first_name ? `, ${user.first_name}` : ""}
        </h1>
        <button onClick={logout} className="text-sm text-gray-500 underline">
          Log out
        </button>
      </div>

      <Link
        to="/projects/new"
        className="mb-4 inline-block rounded bg-black px-4 py-2 text-white"
      >
        + Create Project
      </Link>

      <ErrorBanner error={error} />

      {projects === null && !error && <p className="text-gray-500">Loading projects…</p>}

      {projects?.length === 0 && (
        <p className="text-gray-500">No projects yet — create your first one.</p>
      )}

      <ul className="mt-4 space-y-2">
        {projects?.map((p) => (
          <li key={p.id}>
            <Link
              to={`/projects/${p.id}`}
              className="block rounded border p-3 hover:bg-gray-50"
            >
              <div className="font-medium">{p.name}</div>
              <div className="text-sm text-gray-500">{p.status}</div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
