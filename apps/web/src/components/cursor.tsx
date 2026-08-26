"use client";

// Reticle cursor: the native cursor stays; when the pointer is over an
// interactive target, four bracket-corners spring to frame it — a triage
// "lock-on". Nothing follows the cursor when idle. Disabled on touch and
// under reduced-motion.

import { useEffect, useRef } from "react";

export function Cursor() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fine = window.matchMedia(
      "(hover: hover) and (pointer: fine)",
    ).matches;
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (!fine || reduced) return;

    const el = ref.current!;
    let current: Element | null = null;
    let raf = 0;
    // animated box, eased toward the target rect
    const box = { x: 0, y: 0, w: 0, h: 0, o: 0 };
    const goal = { x: 0, y: 0, w: 0, h: 0, o: 0 };
    const PAD = 6;

    const onMove = (e: PointerEvent) => {
      const target = (e.target as HTMLElement).closest(
        "a, button, [data-target]",
      );
      if (target && target !== current) current = target;
      else if (!target) current = null;

      if (current) {
        const r = current.getBoundingClientRect();
        goal.x = r.left - PAD;
        goal.y = r.top - PAD;
        goal.w = r.width + PAD * 2;
        goal.h = r.height + PAD * 2;
        goal.o = 1;
      } else {
        goal.o = 0;
      }
    };

    const loop = () => {
      const k = 0.25;
      // when hidden, snap size to avoid sweeping across the screen
      if (goal.o === 0) {
        box.o += (0 - box.o) * 0.2;
      } else {
        if (box.o < 0.05) {
          box.x = goal.x;
          box.y = goal.y;
          box.w = goal.w;
          box.h = goal.h;
        }
        box.x += (goal.x - box.x) * k;
        box.y += (goal.y - box.y) * k;
        box.w += (goal.w - box.w) * k;
        box.h += (goal.h - box.h) * k;
        box.o += (1 - box.o) * 0.2;
      }
      el.style.opacity = String(box.o);
      el.style.transform = `translate(${box.x}px, ${box.y}px)`;
      el.style.width = `${box.w}px`;
      el.style.height = `${box.h}px`;
      raf = requestAnimationFrame(loop);
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    raf = requestAnimationFrame(loop);
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={ref} className="reticle hidden md:block" aria-hidden>
      <span />
      <span />
      <span />
      <span />
    </div>
  );
}
