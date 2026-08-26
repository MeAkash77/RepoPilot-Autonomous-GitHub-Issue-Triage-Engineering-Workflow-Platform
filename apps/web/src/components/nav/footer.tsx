import Link from "next/link";
import { PulseMark } from "@/components/brand/logo";
import { StatusDot } from "@/components/micro/status-dot";

const COLS = [
  {
    title: "Product",
    links: [
      ["Demo", "/demo"],
      ["Dashboard", "/dashboard"],
      [
        "Install the app",
        "https://github.com/apps/repopilot-gh/installations/new",
      ],
    ],
  },
  {
    title: "Pipeline",
    links: [
      ["How it works", "/#how"],
      ["Features", "/#features"],
      ["The graph", "/#pipeline"],
    ],
  },
] as const;

export function Footer() {
  return (
    <footer className="border-t border-hairline bg-bg-2">
      <div className="mx-auto max-w-6xl px-6 py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2">
              <PulseMark className="h-5 w-7" />
              <span className="font-mono text-base text-ink">repopilot</span>
            </div>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-dim">
              An autonomous triage engineer for GitHub. It reads every new
              issue, so you don&apos;t have to.
            </p>
            <StatusDot className="mt-5" />
          </div>

          {COLS.map((col) => (
            <div key={col.title}>
              <h3 className="font-mono text-xs uppercase tracking-wider text-ink-faint">
                {col.title}
              </h3>
              <ul className="mt-4 space-y-2.5">
                {col.links.map(([label, href]) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="group inline-flex items-center text-sm text-ink-dim transition-colors hover:text-lime"
                    >
                      <span className="bg-gradient-to-r from-lime to-lime bg-[length:0%_1px] bg-left-bottom bg-no-repeat pb-0.5 transition-[background-size] duration-300 group-hover:bg-[length:100%_1px]">
                        {label}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-hairline pt-6 font-mono text-sm text-ink-faint sm:flex-row">
          <span>© {new Date().getFullYear()} RepoPilot</span>
          <span className="flex items-center gap-2">
            <span className="text-lime">▍</span> press
            <kbd className="rounded-[3px] border border-hairline-bright bg-panel px-1.5 py-0.5 text-xs">
              ⌘K
            </kbd>
            anywhere
          </span>
        </div>
      </div>
    </footer>
  );
}
