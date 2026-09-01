import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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

const EMPTY_FORM = {
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
        <div className="mx-auto w-full max-w-sm animate-fade-in-up">
          <div className="mb-8 flex items-center justify-between lg:hidden">
            <Logo size="md" />
          </div>

          <div className="mb-6 flex items-start justify-between">
            <div>
              <h1 className="font-display text-2xl font-bold text-ink">Create your account</h1>
              <p className="mt-1 text-sm text-ink/60">Start building your brand today.</p>
            </div>
            <Mascot pose={mascotPose} size={48} className="mt-0.5 shrink-0" />
          </div>

          <div className="rounded-sm border-2 border-hairline bg-surface p-6 shadow-sm">
            <GoogleAuthButton
              onSuccess={handleGoogleSuccess}
              onError={() => setError({ message: "Google sign-in failed." })}
              label="Sign up with Google"
            />

            <div className="my-4 flex items-center gap-3">
              <div className="h-px flex-1 bg-hairline" />
              <span className="font-mono text-[10px] uppercase tracking-widest text-ink/40">or</span>
              <div className="h-px flex-1 bg-hairline" />
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <Field
                label="Email"
                type="email"
                value={form.email}
                onChange={set("email")}
                required
                autoFocus
                autoComplete="email"
              />
              <div className="flex gap-2">
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
                className="w-full rounded-sm bg-signal py-2.5 font-display text-xs font-bold uppercase tracking-wide text-white transition hover:bg-signal/90 disabled:opacity-50"
              >
                {loading ? "Registering…" : "Create account"}
              </button>

              <p className="text-center font-mono text-[10px] text-ink/40">
                By continuing, you agree to our Terms &amp; Privacy Policy.
              </p>
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

      <AuthSidePanel tagline="From idea to live domain — fast." />
    </div>
  );
}