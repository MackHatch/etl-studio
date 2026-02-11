import { test, expect } from "@playwright/test";
import path from "path";

const LOGIN_EMAIL = process.env.E2E_LOGIN_EMAIL || "admin@example.com";
const LOGIN_PASSWORD = process.env.E2E_LOGIN_PASSWORD || "adminpassword";

test.describe("Import flow", () => {
  test("full happy path: login -> create dataset -> upload -> mapping -> start -> verify results", async ({
    page,
  }) => {
    await test.step("Login", async () => {
      await page.goto("/login");
      await page.getByTestId("login-email").fill(LOGIN_EMAIL);
      await page.getByTestId("login-password").fill(LOGIN_PASSWORD);
      await page.getByTestId("login-submit").click();
      await expect(page).toHaveURL(/\/datasets/);
    });

    await test.step("Create dataset", async () => {
      await page.getByTestId("nav-datasets").click();
      await page.getByTestId("dataset-create").click();
      await page.getByTestId("dataset-name").fill("E2E Import Test");
      await page.getByTestId("dataset-submit").click();
      await expect(page.getByText("E2E Import Test")).toBeVisible({ timeout: 5000 });
    });

    await test.step("Navigate to dataset and upload sample.csv", async () => {
      await page.getByRole("link", { name: "E2E Import Test" }).click();
      await expect(page).toHaveURL(/\/datasets\/[a-f0-9-]+/);

      const samplePath = path.join(process.cwd(), "public", "sample.csv");
      await page.getByTestId("dataset-file-input").setInputFiles(samplePath);

      await page.waitForURL(/\/runs\/[a-f0-9-]+\/mapping/, { timeout: 10000 });
    });

    await test.step("Configure mapping", async () => {
      await expect(page.getByTestId("mapping-date-select")).toBeVisible({ timeout: 5000 });

      await page.getByTestId("mapping-date-select").selectOption("date");
      await page.getByTestId("mapping-campaign-select").selectOption("campaign");
      await page.getByTestId("mapping-channel-select").selectOption("channel");
      await page.getByTestId("mapping-spend-select").selectOption("spend");

      await page.getByTestId("mapping-save").click();
      await expect(page.getByText("Mapping saved")).toBeVisible({ timeout: 3000 });

      await page.getByTestId("run-start").click();
      await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+$/);
    });

    await test.step("Wait for run to complete", async () => {
      await expect(page.getByTestId("run-sse-status")).toBeVisible({ timeout: 5000 });
      await expect(page.getByTestId("run-progress")).toBeVisible({ timeout: 5000 });

      await expect(page.getByText("SUCCEEDED")).toBeVisible({ timeout: 60000 });
    });

    await test.step("Verify results table populated", async () => {
      await page.getByRole("link", { name: /View results/ }).click();
      await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+\/results/);

      const table = page.getByTestId("results-table");
      await expect(table).toBeVisible();

      const rows = table.locator("tbody tr");
      await expect(rows.first()).toBeVisible({ timeout: 5000 });
      await expect(rows).toHaveCount(3);
    });
  });
});
