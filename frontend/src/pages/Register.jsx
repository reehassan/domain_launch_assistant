import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";

const EMPTY_FORM = {
  username: "",
  email: "",
  password: "",
  first_name: "",
  last_name: "",
};

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(form);
      // register() does not return tokens (contract confirmed) — send the
      // user to /login to actually authenticate, don't pretend they're in.
      navigate("/login", { state: { justRegistered: true } });
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm p-6">
      <h1 className="mb-4 text-xl font-semibold">Register</h1>
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          className="w-full rounded border p-2"
          placeholder="Username"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
          required
        />
        <input
          className="w-full rounded border p-2"
          type="email"
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
        <div className="flex gap-2">
          <input
            className="w-1/2 rounded border p-2"
            placeholder="First name"
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
          />
          <input
            className="w-1/2 rounded border p-2"
            placeholder="Last name"
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
          />
        </div>
        <input
          className="w-full rounded border p-2"
          type="password"
          placeholder="Password (min 8 chars)"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          required
          minLength={8}
        />
        <ErrorBanner error={error} />
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-black p-2 text-white disabled:opacity-50"
        >
          {loading ? "Registering…" : "Register"}
        </button>
      </form>
      <p className="mt-3 text-sm text-gray-600">
        Already have an account? <Link to="/login" className="underline">Log in</Link>
      </p>
    </div>
  );
}
