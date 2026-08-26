/**
 * Records a live dashboard walkthrough for the /demo page video.
 * Run: npx ts-node --esm scripts/record-demo.ts
 * Or:  npx playwright test scripts/record-demo.ts --headed
 *
 * Saves: public/demo/dashboard.webm
 */

import { chromium } from "@playwright/test";
import { encode as encodeJwt } from "next-auth/jwt";
import path from "path";
import fs from "fs";

const BASE = "http://localhost:3000";
const SECRET = "rrQ9gQ4DpQWl1erxP6V9TBcgPpVt2JoSRXn7wsl3WgaH";
const OUT_DIR = path.join(__dirname, "../public/demo");
const OUT_FILE = path.join(OUT_DIR, "dashboard.webm");

async function main() {
  // Build session cookie so middleware lets us through.
  const token = await encodeJwt({
    token: {
      name: "Test User",
      email: "test@example.com",
      login: "testuser",
      sub: "99999999",
    },
    secret: SECRET,
    salt: "authjs.session-token",
    maxAge: 3600,
  });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: {
      dir: OUT_DIR,
      size: { width: 1280, height: 800 },
    },
    colorScheme: "dark",
  });

  await ctx.addCookies([
    {
      name: "authjs.session-token",
      value: token,
      domain: "localhost",
      path: "/",
      httpOnly: true,
      secure: false,
      sameSite: "Lax",
    },
  ]);

  const page = await ctx.newPage();

  const pause = (ms: number) =>
    new Promise((r) => setTimeout(r, ms));

  // ── Overview ─────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/dashboard`, { waitUntil: "networkidle" });
  await pause(2500);

  // ── Runs list ─────────────────────────────────────────────────────────────
  await page.click('a[href="/dashboard/runs"]');
  await page.waitForURL(/\/runs$/);
  await pause(2500);

  // ── Run detail (run 3 — "Large file upload…", bug, awaiting_review) ──────
  await page.click('a[href="/dashboard/runs/3"]');
  await page.waitForURL(/\/runs\/3$/);
  await pause(3500);

  // ── Analytics ─────────────────────────────────────────────────────────────
  await page.click('a[href="/dashboard/analytics"]');
  await page.waitForURL(/\/analytics$/);
  await pause(2500);

  // ── Repos ─────────────────────────────────────────────────────────────────
  await page.click('a[href="/dashboard/repos"]');
  await page.waitForURL(/\/repos$/);
  await pause(2000);

  // ── Back to overview ──────────────────────────────────────────────────────
  await page.click('a[href="/dashboard"]');
  await page.waitForURL(/\/dashboard$/);
  await pause(1500);

  await ctx.close();
  await browser.close();

  // Playwright names the video with a random hash; rename to dashboard.webm.
  const files = fs
    .readdirSync(OUT_DIR)
    .filter((f) => f.endsWith(".webm") && f !== "dashboard.webm")
    .map((f) => ({ f, mt: fs.statSync(path.join(OUT_DIR, f)).mtimeMs }))
    .sort((a, b) => b.mt - a.mt);

  if (files.length > 0) {
    fs.renameSync(path.join(OUT_DIR, files[0].f), OUT_FILE);
    console.log(`✓ saved ${OUT_FILE} (${(fs.statSync(OUT_FILE).size / 1024).toFixed(0)} KB)`);
  } else {
    console.error("✗ no webm found in", OUT_DIR);
    process.exit(1);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
