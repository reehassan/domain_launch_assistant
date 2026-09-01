import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";
import PasswordInput from "../components/PasswordInput";
import Mascot from "../components/Mascot";
import LaunchSuccessModal from "../components/LaunchSuccessModal";
import AuthSidePanel from "../components/AuthSidePanel";
import GoogleAuthButton from "../components/GoogleAuthButton";

const SUCCESS_REDIRECT_DELAY_MS = 1100;

export default function Login() {
  const { login, googleLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const justRegistered = Boolean(location.state?.justRegistered);

  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mascotPose, setMascotPose] = useState("idle");
  const [showSuccess, setShowSuccess] = useState(false);

  function handleSuccess() {
    setMascotPose("celebrating");
    setShowSuccess(true);
    setTimeout(() => navigate("/dashboard"), SUCCESS_REDIRECT_DELAY_MS);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(form);
      handleSuccess();
    } catch (err) {
      setError(parseApiError(err));
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credentialResponse) {
    setError(null);
    try {
      await googleLogin(credentialResponse.credential);
      handleSuccess();
    } catch (err) {
      setError(parseApiError(err));
    }
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <LaunchSuccessModal show={showSuccess} />

      <div className="flex w-full flex-col justify-center px-6 py-12 sm:px-12 lg:w-1/2 lg:px-20">
        <div className="mx-auto w-full max-w-sm animate-fade-in-up">
          <div className="mb-10 flex items-center justify-between lg:hidden">
            <Logo size="md" />
          </div>

          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-ink">
                Welcome back
              </h1>
              <p className="mt-1.5 text-sm text-ink/50">Log in to continue launching.</p>
            </div>
            <Mascot pose={mascotPose} size={48} className="mt-0.5 shrink-0" />
          </div>

          {justRegistered && (
            <div className="mb-6 rounded-lg border border-live/30 bg-live/5 px-4 py-3">
              <p className="font-mono text-xs text-live">
                Account created — log in to continue.
              </p>
            </div>
          )}

          <GoogleAuthButton
            onSuccess={handleGoogleSuccess}
            onError={() => setError({ message: "Google sign-in failed." })}
          />

          <div className="my-6 flex items-center gap-4">
            <div className="h-px flex-1 bg-hairline" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink/35">or</span>
            <div className="h-px flex-1 bg-hairline" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-ink/60">Username</label>
              <input
                className="w-full rounded-lg border border-hairline bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:shadow-[0_0_0_3px_rgba(14,122,80,0.12)]"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                required
                autoFocus
                autoComplete="username"
              />
            </div>

            <PasswordInput
              label="Password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              onFocus={() => setMascotPose("covering")}
              onBlur={() => setMascotPose("idle")}
              required
              autoComplete="current-password"
            />

            <div className="flex justify-end">
              <Link to="#" className="font-mono text-xs text-ink/40 hover:text-signal">
                Forgot password?
              </Link>
            </div>

            <ErrorBanner error={error} />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-signal py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-signal/90 active:scale-[0.99] disabled:opacity-50"
            >
              {loading ? "Logging in…" : "Log in"}
            </button>
          </form>

          <p className="mt-8 text-center text-sm text-ink/50">
            No account?{" "}
            <Link to="/register" className="font-medium text-signal hover:text-signal/80">
              Register
            </Link>
          </p>
        </div>
      </div>

      <AuthSidePanel tagline="Launch your domain in minutes." />
    </div>
  );
}