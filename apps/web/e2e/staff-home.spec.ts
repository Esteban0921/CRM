import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

test('el home de staff muestra métricas y el botón de ingesta', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
  await page.route(/http:\/\/localhost:8000\/family-invoices.*/, async (route) => {
    const url = route.request().url();
    if (url.includes('pending_review')) {
      await route.fulfill({ json: [{ id: '1' }] });
      return;
    }
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/families`, async (route) => {
    await route.fulfill({ json: [{ id: 'f1' }, { id: 'f2' }] });
  });

  await page.goto('/dashboard');

  await expect(page.getByRole('heading', { name: 'Hola, Equipo' })).toBeVisible();
  await expect(page.getByText('Pendientes de revisión')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Procesar correos de prueba' })).toBeVisible();
});
