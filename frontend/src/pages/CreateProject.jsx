import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { createProject } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";

export default function CreateProject() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", business_description: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const project = await createProject(form);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-paper px-4 py-10">
      <div className="mx-auto max-w-lg">
        <Link
          to="/dashboard"
          className="font-mono text-xs uppercase tracking-wider text-ink/40 underline decoration-dotted hover:text-ink"
        >
          ← Back to Dashboard
        </Link>

        <div className="mt-6 mb-6 flex items-center gap-3">
          <Logo size="sm" withWordmark={false} />
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-ink/40">
              New Manifest
            </p>
            <h1 className="font-display text-xl font-bold text-ink">Tell us about the business</h1>
          </div>
        </div>

        <div className="rounded-sm border-2 border-hairline bg-surface p-6 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
                Project name
              </label>
              <input
                className="w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
                placeholder="e.g. Acme Coffee Co."
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
                Business description
              </label>
              <textarea
                className="h-28 w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
                placeholder="What does this business do, and who is it for?"
                value={form.business_description}
                onChange={(e) => setForm({ ...form, business_description: e.target.value })}
                required
              />
            </div>

            <ErrorBanner error={error} />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-sm bg-signal py-2.5 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
            >
              {loading ? "Creating…" : "Create Project"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
