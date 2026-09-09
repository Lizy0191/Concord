import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

/** Deliberately separate from the credential-free, optional-SDK-free UI lane. */
export default defineConfig({
  ...base,
  testIgnore: [],
  outputDir: "test-results-ifc",
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report-ifc" }],
  ],
  testMatch: "**/ifc.spec.ts",
  timeout: 120_000,
  expect: { timeout: 60_000 },
});
