import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
});

test('staff ve el tablero de facturas de proveedor', async ({ page }) => {
  await page.route(`${API}/supplier-invoices`, async (route) => {
    await route.fulfill({
      json: [
        {
          id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          document_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
          supplier_id: null,
          supplier_name: null,
          category: 'fuel',
          amount: '120.00',
          currency: 'EUR',
          issue_date: '2026-09-01',
          due_date: null,
          status: 'pending_review',
          extracted_data: null,
          confidence: 0.4,
        },
      ],
    });
  });
  await page.route(`${API}/suppliers`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/suppliers');

  await expect(page.getByRole('heading', { name: 'Facturas de proveedor' })).toBeVisible();
  await expect(page.getByText('Proveedor sin asignar')).toBeVisible();
  await expect(page.getByText('Combustible', { exact: true })).toBeVisible();
});

test('sin facturas de proveedor, el tablero lo dice claramente', async ({ page }) => {
  await page.route(`${API}/supplier-invoices`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/suppliers`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/suppliers');

  await expect(page.getByText('No hay facturas de proveedor todavía.')).toBeVisible();
});
