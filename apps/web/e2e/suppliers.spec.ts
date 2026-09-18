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

test('staff da de alta un proveedor', async ({ page }) => {
  const suppliers: unknown[] = [];
  await page.route(`${API}/supplier-invoices`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/suppliers`, async (route) => {
    if (route.request().method() === 'POST') {
      const created = {
        id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
        name: 'Repsol',
        tax_id: null,
        email: 'facturas@repsol.com',
        category: 'fuel',
      };
      suppliers.push(created);
      await route.fulfill({ status: 201, json: created });
      return;
    }
    await route.fulfill({ json: suppliers });
  });

  await page.goto('/dashboard/suppliers');
  await page.getByRole('button', { name: 'Nuevo proveedor' }).click();
  await page.getByLabel('Nombre').fill('Repsol');
  await page.getByLabel('Email (para clasificar el buzón)').fill('facturas@repsol.com');
  await page.getByRole('button', { name: 'Añadir proveedor' }).click();

  await expect(page.getByText('Proveedor creado')).toBeVisible();
});
