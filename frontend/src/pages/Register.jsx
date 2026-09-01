import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../hooks/useAuth";
import { parseApiError } from "../api/client";
import ErrorBanner from "../components/ErrorBanner";
import Logo from "../components/Logo";
import PasswordInput from "../components/PasswordInput";
import Mascot from "../components/Mascot";
import LaunchSuccessModal from "../components/LaunchSuccessModal";
import AuthSidePanel from "../components/AuthSidePanel";

const SUCCESS_REDIRECT_DELAY_MS = 1100;

const EMPTY_FORM = {
  email: "",
  password: "",
  first_name: "",
  last_name: "",
};

function Field({ label, ...inputProps }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-ink/60">{label}</label>
      <input
        className="w-full rounded-lg border border-hairline bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-4 focus:ring-signal/10"
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
  const [mascotPose, setMascotPose] = useState("idle");
  const [showSuccess, setShowSuccess] = useState(false);

  function set(field) {
    return (e) => setForm({ ...form, [field]: e.target.value });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register({ ...form, username: form.email });
      navigate("/login", { state: { justRegistered: true } });
    } catch (err) {
      setError(parseApiError(err));
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credentialResponse) {
    setError(null);
    try {
      await googleLogin(credentialResponse.credential);
      setMascotPose("celebrating");
      setShowSuccess(true);
      setTimeout(() => navigate("/dashboard"), SUCCESS_REDIRECT_DELAY_MS);
    } catch (err) {
      setError(parseApiError(err));
    }
  }

  return (
    <div className="flex min-h-screen bg-paper">
      <LaunchSuccessModal show={showSuccess} />

      <div className="flex w-full flex-col justify-center px-6 py-12 sm:px-12 lg:w-1/2 lg:px-20">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-10 flex items-center justify-between lg:hidden">
            <Logo size="md" />
          </div>

          <div className="mb-8 flex items-start justify-between">
            <div>
              <h1 className="font-display text-3xl font-bold text-ink">Create your account</h1>
              <p className="mt-2 text-sm text-ink/50">Start building your brand today.</p>
            </div>
            <Mascot pose={mascotPose} size={52} className="mt-1 shrink-0" />
          </div>

          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError({ message: "Google sign-in failed." })}
            shape="pill"
            size="large"
            width="384"
          />

          <div className="my-6 flex items-center gap-4">
            <div className="h-px flex-1 bg-hairline" />
            <span className="font-mono text-[10px] uppercase tracking-widest text-ink/35">or</span>
            <div className="h-px flex-1 bg-hairline" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Field
              label="Email"
              type="email"
              value={form.email}
              onChange={set("email")}
              required
              autoFocus
              autoComplete="email"
            />
            <div className="flex gap-3">
              <div className="w-1/2">
                <Field
                  label="First name"
                  value={form.first_name}
                  onChange={set("first_name")}
                  autoComplete="given-name"
                />
              </div>
              <div className="w-1/2">
                <Field
                  label="Last name"
                  value={form.last_name}
                  onChange={set("last_name")}
                  autoComplete="family-name"
                />
              </div>
            </div>
            <PasswordInput
              label="Password (min 8 chars)"
              value={form.password}
              onChange={set("password")}
              onFocus={() => setMascotPose("covering")}
              onBlur={() => setMascotPose("idle")}
              required
              minLength={8}
              autoComplete="new-password"
            />

            <ErrorBanner error={error} />

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-signal py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-signal/90 disabled:opacity-50"
            >
              {loading ? "Registering…" : "Create account"}
            </button>

            <p className="text-center font-mono text-[10px] text-ink/40">
              By continuing, you agree to our Terms & Privacy Policy.
            </p>
          </form>

          <p className="mt-8 text-center text-sm text-ink/50">
            Already have an account?{" "}
            <Link to="/login" className="font-medium text-signal hover:text-signal/80">
              Log in
            </Link>
          </p>
        </div>
      </div>

      <AuthSidePanel tagline="From idea to live domain — fast." />
    </div>
  );
}