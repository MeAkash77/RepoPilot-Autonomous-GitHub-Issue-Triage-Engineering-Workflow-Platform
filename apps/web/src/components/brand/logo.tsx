"use client";

// Pulse / triage-vital brand. The mark is an EKG spike — RepoPilot reads a
// repo's vital signs. The wordmark spells "repopilot" with the pulse spike
// standing in for the 'l', so the icon and the name are the same idea.

import { cn } from "@/lib/cn";

/** Standalone EKG mark. Used in nav, loading states, and the favicon. */
export function PulseMark({
  className,
  animate = false,
}: {
  className?: string;
  animate?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 32 24"
      fill="none"
      className={cn("text-lime", className)}
      aria-hidden
    >
      <path
        d="M1 12 H8 L11 12 L13.5 5 L16 19 L18.5 9 L20 12 H31"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        className={animate ? "pulse-draw" : undefined}
        style={{
          filter:
            "drop-shadow(0 0 6px color-mix(in srgb, var(--color-lime) 60%, transparent))",
        }}
      />
    </svg>
  );
}

/** A single tall EKG spike sized to sit inline as a letter (the 'l'). */
function PulseGlyph() {
  return (
    <svg
      viewBox="0 0 12 28"
      fill="none"
      className="inline-block h-[0.82em] w-[0.34em] -translate-y-[0.02em] align-baseline text-lime"
      aria-hidden
    >
      <path
        d="M2 26 L2 16 L5 16 L6.5 3 L8 23 L9.5 16 L10 16"
        stroke="currentColor"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{
          filter:
            "drop-shadow(0 0 5px color-mix(in srgb, var(--color-lime) 55%, transparent))",
        }}
      />
    </svg>
  );
}

/** Full wordmark: repopi + [pulse as 'l'] + ot. */
export function Wordmark({
  className,
  withMark = false,
}: {
  className?: string;
  withMark?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2.5 font-mono text-base font-medium tracking-tight text-ink",
        className,
      )}
    >
      {withMark && <PulseMark className="h-5 w-[28px]" />}
      <span className="inline-flex items-baseline">
        repopi
        <PulseGlyph />
        ot
      </span>
    </span>
  );
}
