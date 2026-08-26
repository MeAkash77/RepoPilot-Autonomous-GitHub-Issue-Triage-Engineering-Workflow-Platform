import type { NextConfig } from "next";
import path from "node:path";

const CSP = [
  "default-src 'self'",
  // Scripts: self + inline (Next.js RSC needs unsafe-inline); no eval.
  "script-src 'self' 'unsafe-inline'",
  // Styles: self + inline (Tailwind / CSS-in-JS).
  "style-src 'self' 'unsafe-inline' https://api.fontshare.com",
  // Fonts: Fontshare CDN.
  "font-src 'self' https://api.fontshare.com https://cdn.fontshare.com",
  // Images: self + GitHub avatars + data URIs (WebGL canvas toDataURL).
  "img-src 'self' data: https://avatars.githubusercontent.com https://github.com",
  // API proxy (same origin) + SSE streams.
  "connect-src 'self'",
  // WebGL shaders need blob workers in some browsers.
  "worker-src 'self' blob:",
  // No framing.
  "frame-ancestors 'none'",
  // No plugins.
  "object-src 'none'",
  // Base URI locked to self.
  "base-uri 'self'",
  // Form posts to self only.
  "form-action 'self'",
].join("; ");

const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "no-referrer" },
  {
    key: "Permissions-Policy",
    value: "geolocation=(), microphone=(), camera=()",
  },
  { key: "Content-Security-Policy", value: CSP },
];

const nextConfig: NextConfig = {
  // Pin the workspace root so Turbopack ignores stray lockfiles higher up.
  turbopack: {
    root: path.join(__dirname),
  },

  async headers() {
    return [
      {
        // Apply to all routes.
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
