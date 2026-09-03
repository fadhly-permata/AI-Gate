import { test, expect } from "@playwright/test";

test("app loads with title + sidebar", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/aigate/);
  await expect(page.locator("aside.sidebar")).toBeVisible();
});
