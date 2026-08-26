"use client";

import * as RT from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export function Tip({
  children,
  label,
  side = "top",
  kbd,
}: {
  children: ReactNode;
  label: string;
  side?: "top" | "bottom" | "left" | "right";
  kbd?: string;
}) {
  return (
    <RT.Provider delayDuration={200}>
      <RT.Root>
        <RT.Trigger asChild>{children}</RT.Trigger>
        <RT.Portal>
          <RT.Content
            side={side}
            sideOffset={8}
            className="z-[120] flex items-center gap-2 rounded-sm border border-hairline-bright bg-panel px-2.5 py-1.5 font-mono text-xs text-ink shadow-xl shadow-black/50 data-[state=delayed-open]:animate-[fade-up_0.15s_ease-out]"
          >
            {label}
            {kbd && (
              <kbd className="rounded-[3px] border border-hairline-bright bg-bg px-1 text-[10px] text-ink-dim">
                {kbd}
              </kbd>
            )}
            <RT.Arrow className="fill-[var(--color-hairline-bright)]" />
          </RT.Content>
        </RT.Portal>
      </RT.Root>
    </RT.Provider>
  );
}
