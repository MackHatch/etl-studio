import { test, expect } from "@playwright/test";
import path from "path";

const LOGIN_EMAIL = process.env.E2E_LOGIN_EMAIL || "admin@example.com";
const LOGIN_PASSWORD = process.env.E2E_LOGIN_PASSWORD || "adminpassword";

test.describe("Compare runs", () => {
  test("create two runs and verify compare page shows diffs", async ({
    page,
  }) => {
    await test.step("Login", async () => {
      await page.goto("/login");
      await page.getByTestId("login-email").fill(LOGIN_EMAIL);
      await page.getByTestId("login-password").fill(LOGIN_PASSWORD);
      await page.getByTestId("login-submit").click();
      await expect(page).toHaveURL(/\/datasets/);
    });

    await test.step("Create dataset and first run", async () => {
      await page.getByTestId("dataset-create").click();
      await page.getByTestId("dataset-name").fill("E2E Compare Test");
      await page.getByTestId("dataset-submit").click();
      await expect(page.getByText("E2E Compare Test")).toBeVisible({ timeout: 5000 });

      await page.getByRole("link", { name: "E2E Compare Test" }).click();
      await expect(page).toHaveURL(/\/datasets\/[a-f0-9-]+/);

      const samplePath = path.join(process.cwd(), "public", "sample.csv");
      await page.getByTestId("dataset-file-input").setInputFiles(samplePath);
      await page.waitForURL(/\/runs\/[a-f0-9-]+\/mapping/, { timeout: 10000 });

      await page.getByTestId("mapping-date-select").selectOption("date");
      await page.getByTestId("mapping-campaign-select").selectOption("campaign");
      await page.getByTestId("mapping-channel-select").selectOption("channel");
      await page.getByTestId("mapping-spend-select").selectOption("spend");
      await page.getByTestId("mapping-save").click();
      await expect(page.getByText("Mapping saved")).toBeVisible({ timeout: 3000 });
      await page.getByTestId("run-start").click();

      await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+$/);
      await expect(page.getByText("SUCCEEDED")).toBeVisible({ timeout: 60000 });
    });

    await test.step("Create second run via Rerun", async () => {
      await page.getByTestId("rerun-button").click();
      await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+$/);
      await page.getByTestId("run-start").click();
      await expect(page.getByText("SUCCEEDED")).toBeVisible({ timeout: 60000 });
    });

    await test.step("Open compare page and verify diff cards", async () => {
      await page.getByTestId("nav-datasets").click();
      await page.getByRole("link", { name: "E2E Compare Test" }).click();
      await expect(page).toHaveURL(/\/datasets\/[a-f0-9-]+/);
      const datasetId = page.url().match(/\/datasets\/([a-f0-9-]+)/)?.[1];
      if (!datasetId) throw new Error("Could not get dataset ID");

      await page.getByTestId("compare-runs-link").click();

      await expect(page.getByTestId("compare-left-select")).toBeVisible({ timeout: 5000 });
      await expect(page.getByTestId("compare-right-select")).toBeVisible();

      await page.getByTestId("compare-left-select").selectOption({ index: 1 });
      await page.getByTestId("compare-right-select").selectOption({ index: 2 });

      await expect(page.getByTestId("compare-diff-cards")).toBeVisible({ timeout: 5000 });
    });
  });
});
