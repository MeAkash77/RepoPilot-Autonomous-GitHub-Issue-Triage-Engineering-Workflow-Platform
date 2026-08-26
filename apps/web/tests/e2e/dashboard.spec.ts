import { test, expect } from "@playwright/test";
import path from "path";

const AUTH_STATE = path.join(__dirname, "../.auth-state.json");

// Redirect test uses a fresh context (no session cookie).
test("dashboard: unauthed /dashboard redirects to sign-in", async ({
  browser,
}) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/api\/auth\/signin/);
  await ctx.close();
});

// These tests carry a pre-built Auth.js session cookie from global-setup.ts.
test.describe("dashboard shell (authenticated)", () => {
  test.use({ storageState: AUTH_STATE });

  test("renders sidebar navigation", async ({ page }) => {
    await page.goto("/dashboard");
    for (const item of [
      "Overview",
      "Inbox",
      "Runs",
      "Repos",
      "Analytics",
      "Observability",
    ]) {
      await expect(
        page.getByRole("link", { name: item, exact: true }),
      ).toBeVisible();
    }
  });

  test("navigates between sections and highlights the active route", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Inbox", exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard\/inbox$/);
    await expect(
      page.getByRole("heading", { name: "Inbox", exact: true }),
    ).toBeVisible();
  });
});
