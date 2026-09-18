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
  await page.route(`${API}/billing/summary`, async (route) => {
    await route.fulfill({
      json: {
        pending_review_count: 1,
        overdue_count: 0,
        families_with_debt: 0,
        families_count: 2,
        overdue_amount: '0.00',
        outstanding_amount: '0.00',
        year_month: '2026-09',
        expected_amount: '90.00',
        collected_amount: '0.00',
        due_soon_count: 0,
        due_soon_amount: '0.00',
        pending_tasks: 0,
        failed_emails: 0,
        unbilled_families: 1,
        currency: 'EUR',
      },
    });
  });
  await page.route(`${API}/billing/at-risk`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/billing/unbilled`, async (route) => {
    await route.fulfill({
      json: [{ id: 'f-hueco', name: 'Familia Hueco', expected_amount: '45.00', currency: 'EUR' }],
    });
  });
  await page.route(`${API}/notifications/inbox`, async (route) => {
    await route.fulfill({
      json: [
        {
          kind: 'pending_review',
          title: 'Facturas por revisar',
          href: '/dashboard/invoices',
          count: 1,
        },
      ],
    });
  });
  await page.route(`${API}/billing/month-report`, async (route) => {
    await route.fulfill({
      json: {
        year_month: '2026-09',
        families: [
          {
            id: 'f-hueco',
            name: 'Familia Hueco',
            expected_amount: '45.00',
            collected_amount: '0.00',
            outstanding_amount: '0.00',
            overdue_amount: '0.00',
            unbilled: true,
            currency: 'EUR',
          },
        ],
      },
    });
  });

  await page.goto('/dashboard');

  await expect(page.getByRole('heading', { name: 'Hola, Equipo' })).toBeVisible();
  await expect(page.getByText('Pendientes de revisión')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Procesar correos de prueba' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Sin facturar este mes' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Crear tareas de facturación' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Cierre 2026-09' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Familia Hueco' }).first()).toBeVisible();
  await page.getByRole('button', { name: 'Avisos' }).click();
  await expect(page.getByRole('link', { name: /Facturas por revisar/ })).toBeVisible();
});
