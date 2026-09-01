// src/components/AuthSidePanel.jsx
import Logo from "./Logo";
import Mascot from "./Mascot";

export default function AuthSidePanel({ tagline, subline }) {
  return (
    <div
      className="relative hidden overflow-hidden lg:flex lg:w-1/2 lg:flex-col lg:justify-between lg:p-12 animate-gradient-drift"
      style={{
        background: "linear-gradient(120deg, #0E7A50, #0F6E7A, #0E7A50)",
        backgroundSize: "200% 200%",
      }}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.09]"
        style={{
          backgroundImage: "radial-gradient(circle, #fff 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />
      <div className="relative">
        <Logo size="md" className="[&_p]:text-white [&_p:last-child]:text-white/50" />
      </div>
      <div className="relative flex flex-1 flex-col items-center justify-center gap-7 text-center">
        <div className="flex h-32 w-32 items-center justify-center rounded-full bg-white/10">
          <Mascot pose="idle" size={92} />
        </div>
        <div className="max-w-sm">
          <div className="mx-auto mb-4 h-px w-10 bg-white/40" />
          <p className="font-display text-2xl font-bold leading-snug text-white">
            {tagline}
          </p>
          {subline && <p className="mt-3 text-sm text-white/60">{subline}</p>}
        </div>
      </div>
      <div className="relative flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-white/35">
        <span className="h-1 w-1 rounded-full bg-live" />
        Domain Launch Assistant
      </div>
    </div>
  );
}