"use client";

// Tactile button — crisp hover/active states, a quick press-down on click, no
// translate-on-hover jiggle. Works as <button> or, with asChild, wraps a Link.

import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/cn";
import type { ComponentProps } from "react";

const VARIANTS = {
  primary:
    "bg-lime text-bg font-medium hover:bg-lime-dim active:brightness-90 glow-lime",
  outline:
    "border border-hairline-bright text-ink-dim hover:border-lime hover:text-lime active:bg-panel",
  ghost: "text-ink-dim hover:text-lime hover:bg-panel",
} as const;

export function Button({
  variant = "primary",
  asChild,
  className,
  ...props
}: ComponentProps<"button"> & {
  variant?: keyof typeof VARIANTS;
  asChild?: boolean;
}) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-sm px-5 py-2.5 font-mono text-sm transition-[background-color,color,border-color,transform] duration-150 active:scale-[0.98]",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
