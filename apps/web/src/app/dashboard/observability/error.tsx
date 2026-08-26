"use client";

import { useEffect } from "react";

export default function ObservabilityError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[observability] client error:", error);
  }, [error]);

  return (
    <div className="fade-up space-y-4">
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Observability
      </h1>
      <div className="rounded-lg border border-danger/30 bg-danger/10 p-6">
        <p className="text-sm font-medium text-danger">
          Something went wrong loading this page
        </p>
        <p className="mt-1 font-mono text-xs text-ink-dim">
          {error.message || "Unknown error"}
        </p>
        {error.digest && (
          <p className="mt-1 font-mono text-[10px] text-ink-faint">
            digest: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="mt-4 rounded-md border border-hairline px-3 py-1.5 text-xs text-ink-dim transition-colors hover:text-ink"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
