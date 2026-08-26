import { test, expect } from "@playwright/test";

test.describe("triage demo", () => {
  test("renders the interactive pipeline graph and the recording", async ({
    page,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto("/demo");
    await expect(
      page.getByRole("heading", { name: /eight stages/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/Large file upload throws an error/i),
    ).toBeVisible();

    // React Flow renders the eight stage nodes.
    for (const node of ["Sanitize", "Classify", "Compose"]) {
      await expect(
        page.locator(".react-flow").getByText(node, { exact: true }),
      ).toBeVisible({ timeout: 10_000 });
    }

    // The recorded dashboard walkthrough is embedded.
    await expect(page.locator("video")).toBeVisible();
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("clicking the Classify node reveals its real output", async ({
    page,
  }) => {
    await page.goto("/demo");
    await page.getByRole("button", { name: /pause/i }).click();
    await page
      .locator(".react-flow")
      .getByText("Classify", { exact: true })
      .click();
    await expect(page.getByText(/90% confident/i)).toBeVisible();
    await expect(page.getByText(/severity 2/i)).toBeVisible();
  });
});
