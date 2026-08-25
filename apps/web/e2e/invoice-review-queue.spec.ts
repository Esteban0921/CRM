import { test, expect } from '@playwright/test';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

const PENDING_INVOICE = {
  id: '55555555-5555-5555-5555-555555555555',
  document_id: '66666666-6666-6666-6666-666666666666',
  family_id: null,
  student_id: null,
  contract_id: null,
  amount: '40.00',
  currency: 'EUR',
  issue_date: '2026-09-01',
  due_date: null,
  status: 'pending_review',
  extracted_data: null,
  confidence: 0.35,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route('**/auth/me', async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
});

test('staff ve la cola de revision y puede marcar una factura como revisada', async ({ page }) => {
  let patched = false;
  await page.route('**/family-invoices?status=pending_review', async (route) => {
    await route.fulfill({ json: patched ? [] : [PENDING_INVOICE] });
  });
  await page.route(`**/family-invoices/${PENDING_INVOICE.id}`, async (route) => {
    patched = true;
    await route.fulfill({ json: { ...PENDING_INVOICE, status: 'sent' } });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByRole('heading', { name: 'Cola de revisión' })).toBeVisible();
  await expect(page.getByText('40.00 EUR')).toBeVisible();
  await expect(page.getByText('35%')).toBeVisible();

  await page.getByRole('button', { name: 'Marcar revisada' }).click();

  await expect(page.getByText('No hay facturas pendientes de revisión.')).toBeVisible();
});

test('sin facturas pendientes, la cola lo dice claramente', async ({ page }) => {
  await page.route('**/family-invoices?status=pending_review', async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByText('No hay facturas pendientes de revisión.')).toBeVisible();
});
