// src/components/GoogleAuthButton.jsx
// Google's own <GoogleLogin> widget can't be restyled to match our
// palette (it only offers light/dark theme presets). We render the real
// widget as a full-size, transparent overlay directly on top of a
// visually-styled button underneath — the user's tap lands on Google's
// real button, it's just invisible. This keeps the actual ID-token flow
// Google issues — GoogleAuthView on the backend verifies that token
// directly — so nothing about the auth contract changes, only the pixels.
//
// IMPORTANT: this used to render the real widget hidden at zero size
// (h-0 w-0 opacity-0) and proxy taps to it via a JS-triggered .click().
// That worked on desktop but silently did nothing on mobile — iOS
// Safari and most mobile browsers only allow the OAuth popup/GSI flow
// to open from a genuinely trusted, direct user gesture, and a
// JS-dispatched click on a hidden element doesn't count as one. Do not
// go back to that pattern.

import { GoogleLogin } from "@react-oauth/google";

function GoogleGlyph() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.69-3.88 2.69-6.62Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.32-1.58-5.03-3.71H.96v2.33A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.97 10.71A5.4 5.4 0 0 1 3.68 9c0-.59.1-1.17.29-1.71V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.83.96 4.04l3.01-2.33Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.46 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.96l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  );
}

export default function GoogleAuthButton({ onSuccess, onError, label = "Continue with Google" }) {
  return (
    <div className="relative">
      {/* Visual layer only — no onClick. The real click is handled by the
          transparent GoogleLogin widget stacked on top of it below. */}
      <div
        aria-hidden="true"
        className="flex w-full items-center justify-center gap-2.5 rounded-sm border border-hairline bg-paper px-4 py-2.5 font-display text-xs font-bold uppercase tracking-wide text-ink/70 transition"
      >
        <GoogleGlyph />
        {label}
      </div>

      {/* Real Google widget, full-size and transparent, positioned exactly
          over the visual button above so the tap is genuinely trusted. */}
      <div className="absolute inset-0 overflow-hidden opacity-0 [&>div]:h-full [&>div]:w-full [&_iframe]:!h-full [&_iframe]:!w-full">
        <GoogleLogin onSuccess={onSuccess} onError={onError} />
      </div>
    </div>
  );
}