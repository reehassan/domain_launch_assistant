// src/components/StampBadge.jsx
// One visual language for "has this stage happened yet" across the whole
// app — done / pending / loading / hold / error all read as one kind of
// object (a stamp), not five different UI patterns.
//
// "hold" (amber) exists as its own variant, not folded into pending or
// error, because the backend already distinguishes: DomainCheck.ERROR
// (infra problem) is not the same thing as DomainCheck.FAIL (a real
// negative result), and a domain result that's neither AVAILABLE nor
// TAKEN isn't "not started yet" either. Collapsing those loses a
// distinction the API is making on purpose.

const VARIANTS = {
  done: { className: "border-live text-live animate-stamp-drop", icon: "✓" },
  pending: { className: "border-dashed border-hairline text-ink/30", icon: "○" },
  loading: { className: "border-wire text-wire animate-stamp-hover", icon: "◌" },
  hold: { className: "border-amber-500 text-amber-600", icon: "!" },
  error: { className: "border-reject text-reject animate-stamp-drop", icon: "✕" },
};

export default function StampBadge({ status = "pending", label }) {
  const variant = VARIANTS[status] ?? VARIANTS.pending;

  return (
    <span
      className={
        "inline-flex shrink-0 items-center gap-1.5 rounded-sm border-2 px-2.5 py-1 " +
        "font-display text-xs font-bold uppercase tracking-wider " +
        variant.className
      }
    >
      <span aria-hidden="true">{variant.icon}</span>
      {label}
    </span>
  );
}
