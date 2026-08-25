import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createProject } from "../api/projects";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";

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
    <div className="mx-auto mt-12 max-w-lg p-6">
      <h1 className="mb-4 text-xl font-semibold">Create Project</h1>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          className="w-full rounded border p-2"
          placeholder="Project name"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          required
        />
        <textarea
          className="h-28 w-full rounded border p-2"
          placeholder="Describe the business…"
          value={form.business_description}
          onChange={(e) => setForm({ ...form, business_description: e.target.value })}
          required
        />
        <ErrorBanner error={error} />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-black p-2 text-white disabled:opacity-50"
        >
          {loading ? "Creating…" : "Create Project"}
        </button>
      </form>
    </div>
  );
}
