"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { PulseMark } from "@/components/brand/logo";
import { StatusDot } from "@/components/micro/status-dot";
import { cn } from "@/lib/cn";

const NAV = [
  ["Overview", "/dashboard", "M3 12l9-9 9 9M5 10v10h14V10"],
  ["Inbox", "/dashboard/inbox", "M4 4h16v12h-5l-3 3-3-3H4z"],
  ["Runs", "/dashboard/runs", "M4 6h16M4 12h16M4 18h10"],
  [
    "Repos",
    "/dashboard/repos",
    "M4 5a2 2 0 012-2h9l5 5v11a2 2 0 01-2 2H6a2 2 0 01-2-2z",
  ],
  ["Analytics", "/dashboard/analytics", "M4 20V10M10 20V4M16 20v-7M22 20H2"],
  [
    "Observability",
    "/dashboard/observability",
    "M12 2a10 10 0 100 20A10 10 0 0012 2zm0 4v4l3 3",
  ],
  [
    "Settings",
    "/dashboard/settings",
    "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z",
  ],
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 z-40 hidden w-56 flex-col border-r border-hairline bg-panel/60 px-4 py-6 backdrop-blur-xl md:flex">
      <Link href="/" className="flex items-center gap-2 px-2">
        <PulseMark className="h-4 w-[22px]" />
        <span className="font-mono text-sm tracking-tight text-ink">
          repopilot
        </span>
      </Link>
      <nav className="mt-10 flex flex-col gap-1">
        {NAV.map(([label, href, path]) => {
          const active =
            href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "text-ink"
                  : "text-ink-dim hover:bg-surface-2 hover:text-ink",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg border border-accent/40 bg-accent/10"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
                className={cn(
                  "relative h-4 w-4 shrink-0",
                  active ? "text-accent" : "text-ink-faint",
                )}
              >
                <path d={path} />
              </svg>
              <span className="relative">{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto space-y-3 px-2">
        <Link
          href="/demo"
          className="block font-mono text-[11px] text-ink-faint transition-colors hover:text-lime"
        >
          ▶ watch demo
        </Link>
        <StatusDot />
        <p className="font-mono text-[10px] text-ink-faint">
          press <kbd className="text-ink-dim">⌘K</kbd>
        </p>
      </div>
    </aside>
  );
}
