// src/components/PasswordInput.jsx
// Password input with a show/hide toggle. Hand-rolled inline SVG icons
// (no icon library in package.json) to match Logo.jsx's own inline-SVG
// approach rather than adding a dependency for two icons.
//
// onFocus/onBlur added so a parent page can drive mascot pose state
// (e.g. Mascot switching to "covering" while this field is focused)
// without PasswordInput needing to know anything about mascots itself.

import { useState } from "react";

function EyeIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a20.6 20.6 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 7 11 7a20.6 20.6 0 0 1-3.22 4.36M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <path d="M1 1l22 22" />
    </svg>
  );
}

export default function PasswordInput({
  label,
  value,
  onChange,
  onFocus,
  onBlur,
  required,
  minLength,
  autoComplete,
}) {
  const [visible, setVisible] = useState(false);

  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] uppercase tracking-widest text-ink/40">
        {label}
      </label>
      <div className="relative">
        <input
          className="w-full rounded-sm border border-hairline bg-paper px-3 py-2 pr-10 text-sm text-ink placeholder:text-ink/30 outline-none transition focus:border-signal focus:ring-1 focus:ring-signal/30"
          type={visible ? "text" : "password"}
          value={value}
          onChange={onChange}
          onFocus={onFocus}
          onBlur={onBlur}
          required={required}
          minLength={minLength}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-ink/40 transition hover:text-ink/70"
          aria-label={visible ? "Hide password" : "Show password"}
          tabIndex={-1}
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
    </div>
  );
}