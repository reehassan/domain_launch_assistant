// src/components/Logo.jsx
import logoBadge from "../assets/logo/logo-badge.png";

const SIZES = {
  sm: { mark: 22, title: "text-sm", sub: "text-[8px]" },
  md: { mark: 32, title: "text-base", sub: "text-[9px]" },
  lg: { mark: 44, title: "text-xl", sub: "text-[10px]" },
};

export default function Logo({ size = "md", withWordmark = true, className = "" }) {
  const s = SIZES[size] ?? SIZES.md;

  return (
    <div className={"flex items-center gap-2.5 " + className}>
      <img src={logoBadge} alt="" width={s.mark} className="shrink-0 object-contain" draggable={false} />
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