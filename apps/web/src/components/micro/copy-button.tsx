"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

export function CopyButton({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={async (e) => {
        e.stopPropagation();
        await navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1400);
      }}
      aria-label="copy"
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded-sm border border-hairline-bright text-ink-faint transition-colors hover:border-lime hover:text-lime",
        className,
      )}
    >
      {copied ? <Check size={12} className="text-lime" /> : <Copy size={12} />}
    </button>
  );
}
