// src/components/Logo.jsx
//
// Original mark for Domain Launch Assistant — not a reproduction of
// any existing company's logo. The idea: an upward launch arrow (the
// "Launch" in the name) sitting inside a rounded green badge, with a
// small dot bitten out of the bottom-right corner standing in for a
// domain's TLD dot (".com", ".ai", etc.) — the two things this app
// actually does, in one mark. Reuses the same wax-stamp/ticket logic
// as StampBadge elsewhere in the app: a badge shape is already this
// product's visual language, so the mark leans into it rather than
// introducing a fourth new shape language.

const SIZES = {
  sm: { mark: 22, title: "text-sm", sub: "text-[8px]" },
  md: { mark: 32, title: "text-base", sub: "text-[9px]" },
  lg: { mark: 44, title: "text-xl", sub: "text-[10px]" },
};

export default function Logo({ size = "md", withWordmark = true, className = "" }) {
  const s = SIZES[size] ?? SIZES.md;

  return (
    <div className={"flex items-center gap-2.5 " + className}>
      <svg
        width={s.mark}
        height={s.mark}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
        className="shrink-0"
      >
        <rect x="1" y="1" width="38" height="38" rx="10" fill="#0E7A50" />
        <path
          d="M20 8.5 L27.5 21 H23 V29.5 H17 V21 H12.5 Z"
          fill="#FFFFFF"
        />
        <circle cx="30.5" cy="30.5" r="3.5" fill="#F6F8F5" stroke="#0E7A50" strokeWidth="1.5" />
      </svg>

      {withWordmark && (
        <div className="leading-none">
          <p className={"font-display font-bold tracking-tight text-ink " + s.title}>
            Domain Launch
          </p>
          <p className={"mt-0.5 font-mono uppercase tracking-[0.2em] text-ink/45 " + s.sub}>
            Assistant
          </p>
        </div>
      )}
    </div>
  );
}
