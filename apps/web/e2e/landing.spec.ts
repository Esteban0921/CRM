import { test, expect } from '@playwright/test';

test('la landing muestra el saludo inicial', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Hello CRM Transporte' })).toBeVisible();
});
