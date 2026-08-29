// src/components/PerforatedDivider.jsx
// The "tear here" line between manifest sections. Bleeds to the card's
// outer edge (-mx-6 assumes px-6 section padding) and bites a notch out
// of each edge to read as a ticket perforation rather than a plain rule.

export default function PerforatedDivider() {
  return (
    <div className="relative -mx-6">
      <div className="perforation" />
      <span className="absolute left-0 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full bg-surface" />
      <span className="absolute right-0 top-1/2 h-4 w-4 translate-x-1/2 -translate-y-1/2 rounded-full bg-surface" />
    </div>
  );
}
