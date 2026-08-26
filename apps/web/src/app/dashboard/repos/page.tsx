"use client";

import { useEffect, useState } from "react";
import type { RepoOut } from "@/lib/api";
import { Card, Empty, SkeletonList } from "@/components/ui";

const LEVELS = [
  {
    value: "suggest",
    label: "Suggest only",
    detail: "Every action waits for human approval. Zero write risk.",
  },
  {
    value: "auto_low_risk",
    label: "Auto low-risk",
    detail:
      "Labels apply automatically; comments and links still need approval.",
  },
  {
    value: "full_auto",
    label: "Full auto",
    detail:
      "Low + medium risk auto-execute. Closing issues ALWAYS needs approval.",
  },
] as const;

export default function ReposPage() {
  const [repos, setRepos] = useState<RepoOut[] | null>(null);

  useEffect(() => {
    fetch("/api/proxy/repos")
      .then((r) => (r.ok ? r.json() : []))
      .then(setRepos)
      .catch(() => setRepos([]));
  }, []);

  async function setLevel(repo: RepoOut, level: string) {
    setRepos(
      (prev) =>
        prev?.map((r) =>
          r.id === repo.id
            ? { ...r, autonomy_level: level as RepoOut["autonomy_level"] }
            : r,
        ) ?? null,
    );
    await fetch(`/api/proxy/repos/${repo.id}/settings`, {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ autonomy_level: level }),
    });
  }

  if (repos === null)
    return (
      <div className="fade-up space-y-6">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Repositories
        </h1>
        <SkeletonList rows={3} />
      </div>
    );

  return (
    <div className="fade-up space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Repositories
        </h1>
        <a
          href="https://github.com/apps/repopilot-gh/installations/new"
          className="rounded-md border border-hairline px-3 py-1.5 text-xs text-ink-dim transition-colors hover:border-ink-faint hover:text-ink"
        >
          + Manage GitHub access
        </a>
      </div>
      {repos.length === 0 ? (
        <Empty
          title="No repos connected"
          body="Install the GitHub App on a repository and it will appear here."
        >
          <a
            href="https://github.com/apps/repopilot-gh/installations/new"
            className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-accent-dim"
          >
            Install GitHub App →
          </a>
        </Empty>
      ) : (
        <div className="space-y-4">
          {repos.map((repo) => (
            <Card key={repo.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-mono text-sm">{repo.full_name}</p>
                  <p className="mt-0.5 text-xs text-ink-faint">
                    {repo.run_count} runs ·{" "}
                    {repo.indexed_at
                      ? `indexed ${new Date(repo.indexed_at).toLocaleString()}`
                      : "not indexed yet"}
                  </p>
                </div>
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-3">
                {LEVELS.map((level) => (
                  <button
                    key={level.value}
                    onClick={() => setLevel(repo, level.value)}
                    className={`rounded-md border p-3 text-left transition-colors ${
                      repo.autonomy_level === level.value
                        ? "border-accent/60 bg-surface-2"
                        : "border-hairline hover:border-ink-faint/40"
                    }`}
                  >
                    <p className="text-sm font-medium">{level.label}</p>
                    <p className="mt-1 text-xs leading-relaxed text-ink-dim">
                      {level.detail}
                    </p>
                  </button>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
