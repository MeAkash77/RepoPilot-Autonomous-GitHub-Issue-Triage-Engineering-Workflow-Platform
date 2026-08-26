/**
 * Playwright config for testing the *live* production deployment.
 *
 * Usage:
 *   LIVE_URL=https://repopilot-steel.vercel.app pnpm exec playwright test \
 *     --config playwright.live.config.ts --project=live
 *
 * Covers only unauthenticated pages (landing, demo, sign-in redirect) since
 * the production site uses real GitHub OAuth and we don't automate that in CI.
 */
import { defineConfig, devices } from "@playwright/test";

const BASE = process.env.LIVE_URL || "https://repopilot-steel.vercel.app";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: ["landing.spec.ts", "demo.spec.ts"],
  fullyParallel: true,
  retries: 2,
  reporter: [["list"], ["json", { outputFile: "playwright-live-results.json" }]],
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "live",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
