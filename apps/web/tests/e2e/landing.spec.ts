import { test, expect } from "@playwright/test";

test.describe("landing page", () => {
  test("renders hero + WebGL field, no console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /reads every issue/i }),
    ).toBeVisible();
    await expect(page.locator("canvas").first()).toBeVisible({
      timeout: 10_000,
    });
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("navbar carries the pulse wordmark and an install CTA", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.locator("header")).toContainText("repopi");
    await expect(
      page.getByRole("link", { name: /install/i }).first(),
    ).toBeVisible();
  });

  test("hero links through to the demo", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: /watch a real triage/i }).click();
    await expect(page).toHaveURL(/\/demo$/);
  });

  test("renders the how-to-use steps and pipeline stages", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText(/Install the GitHub App/i).first(),
    ).toBeVisible();
    await expect(page.getByText(/It triages every new issue/i)).toBeVisible();
    for (const stage of ["sanitize", "classify", "compose"]) {
      await expect(page.getByText(stage, { exact: false }).first()).toBeVisible();
    }
  });

  test("command palette opens on Meta+K", async ({ page }) => {
    await page.goto("/");
    await page.keyboard.press("Meta+k");
    await expect(page.locator("[cmdk-root]")).toBeVisible();
    await expect(page.getByText(/Watch the demo/i)).toBeVisible();
  });
});
