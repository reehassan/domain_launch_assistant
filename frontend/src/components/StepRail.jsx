// frontend/src/components/StepRail.jsx
//
// The persistent "you are here" progress rail for the 4-step launch
// flow. Structurally replaces implicit scroll position (the old
// ProjectDetails rendered all four sections in one long stack) with an
// explicit state machine: each step is done / current / locked, and
// "done" steps are clickable so the founder can jump back and review
// a prior choice without losing their place in the flow.
//
// This component is dumb on purpose — it doesn't know *why* a step is
// done, only what it's told. ProjectDetails computes `frontierKey` from
// project state and owns the click handler.

const CONNECTOR = "flex-1 h-px";

export default function StepRail({ steps, frontierIndex, viewIndex, onSelect }) {
  return (
    <div className="px-6 pt-5">
      <div className="flex items-center">
        {steps.map((step, i) => {
          const isDone = i < frontierIndex;
          const isCurrent = i === frontierIndex;
          const isLocked = i > frontierIndex;
          const isViewed = i === viewIndex;
          const clickable = isDone || isCurrent;
          return (
            <div key={step.key} className="flex flex-1 items-center last:flex-none">
              <button
                type="button"
                disabled={!clickable}
                onClick={() => clickable && onSelect(step.key)}
                className="flex flex-col items-center gap-1.5 disabled:cursor-not-allowed"
              >
                <span
                  className={
                    "flex h-7 w-7 items-center justify-center rounded-full border-2 font-mono text-xs transition " +
                    (isDone
                      ? "border-live bg-live/10 text-live animate-stamp-drop"
                      : isCurrent
                      ? "border-signal bg-signal/10 text-signal"
                      : "border-hairline text-ink/25") +
                    (isViewed ? " ring-2 ring-offset-2 ring-offset-surface ring-ink/30" : "")
                  }
                >
                  {isDone ? "✓" : i + 1}
                </span>
                <span
                  className={
                    "font-display text-[10px] font-bold uppercase tracking-wider " +
                    (isLocked ? "text-ink/25" : isCurrent ? "text-signal" : "text-ink/60")
                  }
                >
                  {step.label}
                </span>
              </button>
              {i < steps.length - 1 && (
                <span
                  className={
                    CONNECTOR + " mx-2 mb-4 " + (i < frontierIndex ? "bg-live/40" : "bg-hairline")
                  }
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}