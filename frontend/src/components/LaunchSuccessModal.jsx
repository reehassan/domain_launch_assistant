// src/components/LaunchSuccessModal.jsx
// Shown briefly after a successful login/registration, before redirecting
// to /dashboard. Reuses the existing stamp-drop keyframe already defined
// in tailwind.config.js — no new animation needed.

import Mascot from "./Mascot";

export default function LaunchSuccessModal({ show }) {
  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm">
      <div className="animate-stamp-drop rounded-sm border-2 border-hairline bg-surface px-8 py-7 text-center shadow-lg">
        <div className="flex justify-center">
          <Mascot pose="celebrating" size={84} />
        </div>
        <p className="mt-4 font-display text-lg font-bold text-ink">
          Let&apos;s launch your business 🚀
        </p>
        <p className="mt-1 font-mono text-xs text-ink/50">Taking you to your dashboard…</p>
      </div>
    </div>
  );
}