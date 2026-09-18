import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

test('staff busca y ve resultados agrupados', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
  await page.route(`${API}/search*`, async (route) => {
    await route.fulfill({
      json: {
        hits: [
          {
            type: 'family',
            id: '22222222-2222-2222-2222-222222222222',
            title: 'Familia Garcia',
            subtitle: 'Calle Falsa 123',
            family_id: '22222222-2222-2222-2222-222222222222',
          },
        ],
      },
    });
  });

  await page.goto('/dashboard/search?q=Garcia');

  await expect(page.getByRole('heading', { name: 'Buscar' })).toBeVisible();
  await expect(page.getByText('Familia Garcia')).toBeVisible();
  await expect(page.getByText('Calle Falsa 123')).toBeVisible();
});
