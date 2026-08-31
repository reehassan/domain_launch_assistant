import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../hooks/useAuth";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";

const EMPTY_FORM = {
  username: "",
  email: "",
  password: "",
  first_name: "",
  last_name: "",
};

function Field({ label, ...inputProps }) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
        {label}
      </label>
      <input
        className="w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
        {...inputProps}
      />
    </div>
  );
}

export default function Register() {
  const { register, googleLogin } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(form);
      // register() does not return tokens — send the user to /login to
      // actually authenticate, don't pretend they're in.
      navigate("/login", { state: { justRegistered: true } });
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credentialResponse) {
    setError(null);
    try {
      // Google sign-up logs the user in directly (backend creates the
      // account on the fly) — unlike the form path above, no /login
      // redirect needed.
      await googleLogin(credentialResponse.credential);
      navigate("/dashboard");
    } catch (err) {
      setError(parseApiError(err));
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo size="lg" />
        </div>

        <div className="rounded-sm border-2 border-hairline bg-surface p-6 shadow-sm">
          <h1 className="font-display text-lg font-bold text-ink">Create an account</h1>
          <p className="mt-1 text-sm text-ink/60">Start filing your first manifest.</p>

          <div className="mt-5 flex justify-center">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => setError({ message: "Google sign-in failed." })}
            />
          </div>

          <div className="my-4 flex items-center gap-3">
            <div className="h-px flex-1 bg-hairline" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink/40">or</span>
            <div className="h-px flex-1 bg-hairline" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <Field
              label="Username"
              value={form.username}
              onChange={set("username")}
              required
              autoFocus
            />
            <Field
              label="Email"
              type="email"
              value={form.email}
              onChange={set("email")}
              required
            />
            <div className="flex gap-2">
              <div className="w-1/2">
                <Field label="First name" value={form.first_name} onChange={set("first_name")} />
              </div>
              <div className="w-1/2">
                <Field label="Last name" value={form.last_name} onChange={set("last_name")} />
              </div>
            </div>
            <Field
              label="Password (min 8 chars)"
              type="password"
              value={form.password}
              onChange={set("password")}
              required
              minLength={8}
            />

            <ErrorBanner error={error} />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-sm bg-signal py-2.5 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
            >
              {loading ? "Registering…" : "Register"}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center font-mono text-xs text-ink/50">
          Already have an account?{" "}
          <Link to="/login" className="text-signal underline decoration-dotted hover:text-signal/80">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}