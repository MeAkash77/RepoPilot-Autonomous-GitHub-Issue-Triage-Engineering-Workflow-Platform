"use client";

// ⌘K command palette. Global launcher for navigation and key actions, themed
// to the phosphor system. Opens on ⌘K / Ctrl-K or "/".

import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  PlayCircle,
  Download,
  Home,
  Inbox,
  GitPullRequestArrow,
  Boxes,
  BarChart3,
} from "lucide-react";

const INSTALL_URL = "https://github.com/apps/repopilot-gh/installations/new";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || e.key === "/") {
        const tag = (e.target as HTMLElement)?.tagName;
        if (e.key === "/" && (tag === "INPUT" || tag === "TEXTAREA")) return;
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      className="fixed left-1/2 top-[20%] z-[130] w-[min(92vw,560px)] -translate-x-1/2 overflow-hidden rounded-lg border border-hairline-bright bg-panel shadow-2xl shadow-black/60"
      overlayClassName="fixed inset-0 z-[125] bg-bg/70 backdrop-blur-sm data-[state=open]:animate-[fade-up_0.15s_ease-out]"
    >
      <div className="flex items-center gap-2 border-b border-hairline px-4">
        <span className="font-mono text-xs text-lime">›</span>
        <Command.Input
          placeholder="Search or jump to…"
          className="h-12 flex-1 bg-transparent font-mono text-sm text-ink outline-none placeholder:text-ink-faint"
        />
        <kbd className="rounded-[3px] border border-hairline-bright bg-bg px-1.5 py-0.5 font-mono text-[10px] text-ink-faint">
          esc
        </kbd>
      </div>
      <Command.List className="max-h-80 overflow-y-auto p-2">
        <Command.Empty className="px-3 py-6 text-center font-mono text-xs text-ink-faint">
          no matches
        </Command.Empty>

        <Group heading="navigate">
          <Item icon={<Home size={15} />} onSelect={() => go("/")}>
            Home
          </Item>
          <Item icon={<PlayCircle size={15} />} onSelect={() => go("/demo")}>
            Watch the demo
          </Item>
          <Item
            icon={<LayoutDashboard size={15} />}
            onSelect={() => go("/dashboard")}
          >
            Dashboard · Overview
          </Item>
          <Item
            icon={<Inbox size={15} />}
            onSelect={() => go("/dashboard/inbox")}
          >
            Dashboard · Inbox
          </Item>
          <Item
            icon={<GitPullRequestArrow size={15} />}
            onSelect={() => go("/dashboard/runs")}
          >
            Dashboard · Runs
          </Item>
          <Item
            icon={<Boxes size={15} />}
            onSelect={() => go("/dashboard/repos")}
          >
            Dashboard · Repos
          </Item>
          <Item
            icon={<BarChart3 size={15} />}
            onSelect={() => go("/dashboard/analytics")}
          >
            Dashboard · Analytics
          </Item>
        </Group>

        <Group heading="actions">
          <Item
            icon={<Download size={15} />}
            onSelect={() => {
              setOpen(false);
              window.location.href = INSTALL_URL;
            }}
          >
            Install the GitHub App
          </Item>
        </Group>
      </Command.List>
    </Command.Dialog>
  );
}

function Group({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <Command.Group
      heading={heading}
      className="px-2 pb-2 font-mono text-[10px] uppercase tracking-wider text-ink-faint [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5"
    >
      {children}
    </Command.Group>
  );
}

function Item({
  icon,
  children,
  onSelect,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-sm px-3 py-2 font-sans text-sm text-ink-dim transition-colors data-[selected=true]:bg-lime/10 data-[selected=true]:text-lime"
    >
      <span className="text-ink-faint">{icon}</span>
      {children}
    </Command.Item>
  );
}
