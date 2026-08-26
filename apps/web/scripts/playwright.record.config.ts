import { defineConfig, devices } from "@playwright/test";
import path from "path";

export default defineConfig({
  testDir: path.join(__dirname),
  testMatch: "record-demo.spec.ts",
  globalSetup: "../tests/global-setup.ts",
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "off",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
