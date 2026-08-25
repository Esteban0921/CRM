import { test, expect } from '@playwright/test';

test('la landing muestra el nombre del producto y enlaza al login', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'CRM Transporte' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Iniciar sesión' })).toBeVisible();
});
