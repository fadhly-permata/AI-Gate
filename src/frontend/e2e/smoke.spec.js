import { test, expect } from "@playwright/test";

test("app loads with title + sidebar", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/aigate/);
  await expect(page.locator("aside.sidebar")).toBeVisible();
});

test("gateway backend answers health + providers", async ({ request }) => {
  // Memvalidasi webServer (run.py) benar-benar melayani API, bukan cuma UI.
  const health = await request.get("/api/health");
  expect(health.ok()).toBeTruthy();

  const providers = await request.get("/api/providers");
  expect(providers.ok()).toBeTruthy();
  const body = await providers.json();
  expect(body).toHaveProperty("object", "list");
});
