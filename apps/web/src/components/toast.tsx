"use client";

// Minimal toast system: a module-level emitter plus a <Toaster> that renders
// the stack. Call toast("…") from anywhere; no context provider needed.

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

type Tone = "ok" | "danger" | "info";
interface Toast {
  id: number;
  message: string;
  tone: Tone;
}

let counter = 0;
const listeners = new Set<(t: Toast) => void>();

export function toast(message: string, tone: Tone = "info") {
  const t = { id: ++counter, message, tone };
  listeners.forEach((l) => l(t));
}

const TONE: Record<Tone, string> = {
  ok: "border-ok/40 text-ok",
  danger: "border-danger/40 text-danger",
  info: "border-hairline text-ink",
};

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const onToast = (t: Toast) => {
      setToasts((prev) => [...prev, t]);
      setTimeout(
        () => setToasts((prev) => prev.filter((x) => x.id !== t.id)),
        2600,
      );
    };
    listeners.add(onToast);
    return () => {
      listeners.delete(onToast);
    };
  }, []);

  return (
    <div className="pointer-events-none fixed bottom-6 right-6 z-[100] flex flex-col gap-2">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.96 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "pointer-events-auto rounded-lg border bg-surface px-4 py-2.5 text-sm shadow-xl shadow-black/40 backdrop-blur-xl",
              TONE[t.tone],
            )}
          >
            {t.message}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
