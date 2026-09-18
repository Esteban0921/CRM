import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

test('staff ve la cola de notas de crédito vacía con un empty state', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
  await page.route(`${API}/documents*`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/credit-notes');

  await expect(page.getByRole('heading', { name: 'Notas de crédito' })).toBeVisible();
  await expect(page.getByText('No hay notas de crédito.')).toBeVisible();
});
