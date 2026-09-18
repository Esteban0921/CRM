import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

test('staff ve la bandeja de correos ingeridos', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({
      json: {
        id: '11111111-1111-1111-1111-111111111111',
        email: 'staff@example.com',
        name: 'Equipo',
        role: 'staff',
        family_id: null,
      },
    });
  });
  await page.route(`${API}/emails`, async (route) => {
    await route.fulfill({
      json: [
        {
          id: 'e1',
          gmail_id: 'g1',
          subject: 'Factura de prueba',
          from_address: 'admin@crm-transporte.local',
          processing_status: 'processed',
          error_message: null,
          created_at: '2026-09-15T10:00:00Z',
          document_count: 1,
        },
      ],
    });
  });

  await page.goto('/dashboard/emails');

  await expect(page.getByRole('heading', { name: 'Correos ingeridos' })).toBeVisible();
  await expect(page.getByText('Factura de prueba')).toBeVisible();
});
