/**
 * One-shot dashboard recording. Run with:
 *   npx playwright test scripts/record-demo.spec.ts --project=chromium
 * Video saved to public/demo/dashboard.webm automatically.
 */
import { test } from "@playwright/test";
import fs from "fs";
import path from "path";

const AUTH_STATE = path.join(__dirname, "../tests/.auth-state.json");
const OUT = path.join(__dirname, "../public/demo/dashboard.webm");

let capturedVideoPath: string | undefined;

test.use({
  storageState: AUTH_STATE,
  // 2560×1440 (QHD) viewport — video canvas matches exactly, no gray bars.
  // deviceScaleFactor:2 gives HiDPI sub-pixel rendering inside that frame.
  viewport: { width: 2560, height: 1440 },
  deviceScaleFactor: 2,
  colorScheme: "dark",
  // Let recordVideo default to viewport dimensions so content fills the frame.
  video: { mode: "on", size: { width: 2560, height: 1440 } },
  baseURL: "http://localhost:3000",
});

const pause = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

test("record dashboard walkthrough", async ({ page }) => {
  // Overview — let counters and stat cards fully render
  await page.goto("/dashboard", { waitUntil: "networkidle" });
  await pause(3500);
  await page.evaluate(() => window.scrollBy({ top: 320, behavior: "smooth" }));
  await pause(1800);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(1000);

  // Runs list
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await page.waitForURL(/\/runs$/);
  await pause(3000);

  // Run detail — "Large file upload…", bug sev-2, awaiting_review
  await page.goto("/dashboard/runs/3", { waitUntil: "networkidle" });
  await pause(3500);
  await page.evaluate(() => window.scrollBy({ top: 550, behavior: "smooth" }));
  await pause(2000);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await pause(800);

  // Analytics
  await page.getByRole("link", { name: "Analytics", exact: true }).click();
  await page.waitForURL(/\/analytics$/);
  await pause(3000);

  // Repos
  await page.getByRole("link", { name: "Repos", exact: true }).click();
  await page.waitForURL(/\/repos$/);
  await pause(2500);

  // Return to overview — closing shot
  await page.getByRole("link", { name: "Overview", exact: true }).click();
  await page.waitForURL(/\/dashboard$/);
  await pause(2500);
});

// video().path() resolves only after context closes → grab in afterEach
test.afterEach(async ({ page }) => {
  capturedVideoPath = await page.video()?.path();
});

test.afterAll(async () => {
  if (!capturedVideoPath || !fs.existsSync(capturedVideoPath)) {
    console.error("✗ video file not found");
    return;
  }
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.copyFileSync(capturedVideoPath, OUT);
  const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
  console.log(`\n✓ dashboard.webm saved (${kb} KB) → ${OUT}\n`);
});
