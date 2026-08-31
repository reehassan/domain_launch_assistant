import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../hooks/useAuth";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";

export default function Login() {
  const { login, googleLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const justRegistered = Boolean(location.state?.justRegistered);

  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(form);
      navigate("/dashboard");
    } catch (err) {
      setError(parseApiError(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credentialResponse) {
    setError(null);
    try {
      await googleLogin(credentialResponse.credential);
      navigate("/dashboard");
    } catch (err) {
      setError(parseApiError(err));
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Logo size="lg" />
        </div>

        <div className="rounded-sm border-2 border-hairline bg-surface p-6 shadow-sm">
          <h1 className="font-display text-lg font-bold text-ink">Log in</h1>
          <p className="mt-1 text-sm text-ink/60">Pick up where you left off.</p>

          {justRegistered && (
            <div className="mt-4 rounded-sm border border-live/40 bg-live/5 px-3 py-2">
              <p className="font-mono text-xs text-live">
                Account created — log in to continue.
              </p>
            </div>
          )}

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
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
                Username
              </label>
              <input
                className="w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
                Password
              </label>
              <input
                className="w-full rounded-sm border border-hairline bg-paper px-3 py-2 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>

            <ErrorBanner error={error} />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-sm bg-signal py-2.5 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
            >
              {loading ? "Logging in…" : "Log in"}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center font-mono text-xs text-ink/50">
          No account?{" "}
          <Link to="/register" className="text-signal underline decoration-dotted hover:text-signal/80">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}