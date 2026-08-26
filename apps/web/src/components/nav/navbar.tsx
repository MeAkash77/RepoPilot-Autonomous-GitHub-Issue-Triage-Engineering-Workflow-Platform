"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { LayoutDashboard, LogOut } from "lucide-react";
import { Wordmark } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

const SECTIONS = [
  ["why", "Why"],
  ["features", "Features"],
  ["how", "How it works"],
  ["pipeline", "Pipeline"],
] as const;

const INSTALL_URL = "https://github.com/apps/repopilot-gh/installations/new";

export function Navbar() {
  const [active, setActive] = useState<string>("");
  const [scrolled, setScrolled] = useState(false);
  const { data: session, status } = useSession();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) if (e.isIntersecting) setActive(e.target.id);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    SECTIONS.forEach(([id]) => {
      const el = document.getElementById(id);
      if (el) obs.observe(el);
    });
    return () => {
      window.removeEventListener("scroll", onScroll);
      obs.disconnect();
    };
  }, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 border-b transition-colors duration-300",
        scrolled
          ? "border-hairline bg-bg/80 backdrop-blur-md"
          : "border-transparent bg-transparent",
      )}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" aria-label="repopilot home">
          <Wordmark withMark />
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {SECTIONS.map(([id, label]) => (
            <a
              key={id}
              href={`#${id}`}
              className={cn(
                "relative rounded-sm px-3 py-1.5 font-mono text-sm transition-colors",
                active === id ? "text-lime" : "text-ink-dim hover:text-ink",
              )}
            >
              {label}
              {active === id && (
                <span className="absolute inset-x-3 -bottom-px h-px bg-lime shadow-[0_0_6px] shadow-lime" />
              )}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          {status === "authenticated" ? (
            <>
              <Link
                href="/dashboard"
                className="flex items-center gap-1.5 rounded-sm border border-hairline-bright bg-panel px-3 py-2 font-mono text-sm text-ink-dim transition-colors hover:border-lime hover:text-lime"
              >
                <LayoutDashboard size={13} />
                Dashboard
              </Link>
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button className="flex items-center gap-2 rounded-sm border border-hairline-bright bg-panel px-2 py-2 font-mono text-sm text-ink-dim transition-colors hover:border-lime hover:text-lime">
                    {session.user?.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={session.user.image}
                        alt=""
                        className="h-5 w-5 rounded-full"
                      />
                    ) : (
                      <span className="h-5 w-5 rounded-full bg-lime/20" />
                    )}
                  </button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    sideOffset={8}
                    align="end"
                    className="z-[120] min-w-44 rounded-sm border border-hairline-bright bg-panel p-1 font-mono text-sm shadow-xl shadow-black/50"
                  >
                    <DropdownMenu.Item asChild>
                      <a
                        href={INSTALL_URL}
                        className="flex cursor-pointer items-center gap-2 rounded-sm px-2.5 py-2 text-ink-dim outline-none data-[highlighted]:bg-lime/10 data-[highlighted]:text-lime"
                      >
                        + Manage repos
                      </a>
                    </DropdownMenu.Item>
                    <DropdownMenu.Item asChild>
                      <Link
                        href="/dashboard/settings"
                        className="flex cursor-pointer items-center gap-2 rounded-sm px-2.5 py-2 text-ink-dim outline-none data-[highlighted]:bg-lime/10 data-[highlighted]:text-lime"
                      >
                        Settings
                      </Link>
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      onSelect={() => signOut({ callbackUrl: "/" })}
                      className="flex cursor-pointer items-center gap-2 rounded-sm px-2.5 py-2 text-ink-dim outline-none data-[highlighted]:bg-red/10 data-[highlighted]:text-red"
                    >
                      <LogOut size={13} /> Sign out
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </>
          ) : (
            <>
              <button
                onClick={() => signIn("github")}
                className="hidden rounded-sm px-3 py-2 font-mono text-sm text-ink-dim transition-colors hover:text-lime sm:block"
              >
                sign in
              </button>
              <Button asChild variant="primary">
                <a href={INSTALL_URL} target="_blank" rel="noreferrer">
                  Install
                </a>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
