"use client";

import Link from "next/link";
import { signOut } from "next-auth/react";
import { useSession } from "next-auth/react";
import { Card } from "@/components/ui";

const INSTALL_URL = "https://github.com/apps/repopilot-gh/installations/new";

export default function SettingsPage() {
  const { data: session } = useSession();

  return (
    <div className="fade-up space-y-8 max-w-2xl">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Settings
      </h1>

      {/* Account */}
      <section className="space-y-3">
        <h2 className="font-mono text-xs uppercase tracking-widest text-ink-faint">
          Account
        </h2>
        <Card className="flex items-center gap-4">
          {session?.user?.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={session.user.image}
              alt=""
              className="h-10 w-10 rounded-full"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="font-mono text-sm text-ink">
              {session?.user?.name ?? session?.user?.login ?? "—"}
            </p>
            <p className="font-mono text-xs text-ink-faint">
              @{session?.user?.login ?? "—"}
            </p>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/" })}
            className="rounded-md border border-hairline px-3 py-1.5 font-mono text-xs text-ink-dim transition-colors hover:border-danger/40 hover:text-danger"
          >
            Sign out
          </button>
        </Card>
      </section>

      {/* GitHub access */}
      <section className="space-y-3">
        <h2 className="font-mono text-xs uppercase tracking-widest text-ink-faint">
          GitHub App Access
        </h2>
        <Card className="space-y-4">
          <div>
            <p className="text-sm text-ink">Manage repository access</p>
            <p className="mt-1 text-xs text-ink-dim">
              Add or remove repositories, change which repos RepoPilot can
              triage, or uninstall the app entirely — all on GitHub.
            </p>
          </div>
          <a
            href={INSTALL_URL}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2 font-mono text-sm font-medium text-black transition-colors hover:bg-accent/90"
          >
            Manage GitHub access →
          </a>
        </Card>
      </section>

      {/* Repos shortcut */}
      <section className="space-y-3">
        <h2 className="font-mono text-xs uppercase tracking-widest text-ink-faint">
          Repository settings
        </h2>
        <Card className="space-y-4">
          <div>
            <p className="text-sm text-ink">Autonomy levels</p>
            <p className="mt-1 text-xs text-ink-dim">
              Configure how much RepoPilot can do automatically per repo —
              suggest only, auto low-risk, or full auto.
            </p>
          </div>
          <Link
            href="/dashboard/repos"
            className="inline-flex items-center gap-2 rounded-md border border-hairline px-4 py-2 font-mono text-sm text-ink-dim transition-colors hover:border-accent/40 hover:text-ink"
          >
            Open Repositories →
          </Link>
        </Card>
      </section>
    </div>
  );
}
