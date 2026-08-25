import { defineConfig } from '@playwright/test';

const port = Number(process.env.E2E_PORT ?? 4123);
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `next start -H 127.0.0.1 -p ${port}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
