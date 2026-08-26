"use client";

import dynamic from "next/dynamic";

// Client-only WebGL accent with a CSS fallback so the section is never blank
// before the canvas mounts (or on machines where it won't).
const ShaderField = dynamic(
  () => import("./shader-field").then((m) => m.ShaderField),
  {
    ssr: false,
    loading: () => (
      <div className="absolute inset-0">
        <div className="radial-lime absolute left-1/2 top-1/3 h-[55vh] w-[55vh] -translate-x-1/2 opacity-40" />
      </div>
    ),
  },
);

export function ShaderFieldLazy({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute inset-0 ${className}`}
    >
      <ShaderField />
    </div>
  );
}
