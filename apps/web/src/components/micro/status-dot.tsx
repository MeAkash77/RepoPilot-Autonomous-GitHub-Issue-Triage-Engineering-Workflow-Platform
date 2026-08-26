"use client";

// Live system-status pill. Pings the API health endpoint through the BFF
// proxy and shows operational / degraded. Polls gently.

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

type State = "up" | "down" | "checking";

export function StatusDot({ className }: { className?: string }) {
  const [state, setState] = useState<State>("checking");

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const r = await fetch("/api/status", { cache: "no-store" });
        if (alive) setState(r.ok ? "up" : "down");
      } catch {
        if (alive) setState("down");
      }
    };
    check();
    const id = setInterval(check, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const tone =
    state === "up" ? "bg-lime" : state === "down" ? "bg-red" : "bg-amber";
  const label =
    state === "up"
      ? "all systems operational"
      : state === "down"
        ? "api unreachable"
        : "checking…";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 font-mono text-[11px] text-ink-faint",
        className,
      )}
    >
      <span className="relative flex h-2 w-2">
        {state === "up" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-lime opacity-60" />
        )}
        <span
          className={cn("relative inline-flex h-2 w-2 rounded-full", tone)}
        />
      </span>
      {label}
    </span>
  );
}
