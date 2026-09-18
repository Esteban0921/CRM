import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

test('staff ve la bandeja global de tareas', async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
  await page.route(`${API}/tasks`, async (route) => {
    await route.fulfill({
      json: [
        {
          id: 't1',
          family_id: '22222222-2222-2222-2222-222222222222',
          family_name: 'Familia Garcia',
          title: 'El padre indica que ha pagado',
          description: 'invoice:55555555-5555-5555-5555-555555555555 · 45.00 EUR',
          due_date: '2026-09-20',
          status: 'pending',
          assigned_to: null,
          created_by: STAFF_ME.id,
        },
      ],
    });
  });

  await page.route(
    `${API}/family-invoices/55555555-5555-5555-5555-555555555555/confirm-payment`,
    async (route) => {
      await route.fulfill({
        json: {
          id: '55555555-5555-5555-5555-555555555555',
          status: 'paid',
        },
      });
    },
  );

  await page.goto('/dashboard/tasks');

  await expect(page.getByRole('heading', { name: 'Tareas' })).toBeVisible();
  await expect(page.getByText('El padre indica que ha pagado')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Familia Garcia' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Confirmar cobro' })).toBeVisible();
});
