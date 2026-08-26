import { test, expect } from '@playwright/test';

// Ver el comentario equivalente en families.spec.ts: las rutas mockeadas se
// anclan al origen de la API, no a "**/family-invoices".
const API = 'http://localhost:8000';

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
  family_id: '77777777-7777-7777-7777-777777777777',
  family_name: 'Familia Garcia',
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

const PAID_INVOICE = {
  ...PENDING_INVOICE,
  id: '88888888-8888-8888-8888-888888888888',
  family_id: '99999999-9999-9999-9999-999999999999',
  family_name: 'Familia Lopez',
  status: 'paid',
  confidence: null,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
});

test('staff ve las facturas organizadas en un tablero por estado', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [PENDING_INVOICE, PAID_INVOICE] });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByRole('heading', { name: 'Cola de revisión' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pendiente de revisión' })).toBeVisible();
  await expect(page.getByText('Familia Garcia')).toBeVisible();
  await expect(page.getByText('35% confianza')).toBeVisible();
  await expect(page.getByText('Familia Lopez')).toBeVisible();
});

test('staff puede cambiar el estado de una factura desde su tarjeta', async ({ page }) => {
  let patchedBody: Record<string, unknown> | null = null;
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [PENDING_INVOICE] });
  });
  await page.route(`${API}/family-invoices/${PENDING_INVOICE.id}`, async (route) => {
    patchedBody = JSON.parse(route.request().postData() ?? '{}');
    await route.fulfill({ json: { ...PENDING_INVOICE, ...patchedBody } });
  });

  await page.goto('/dashboard/invoices');
  await page.getByLabel('Cambiar estado de la factura de Familia Garcia').selectOption('sent');

  await expect.poll(() => patchedBody?.status).toBe('sent');
});

test('sin facturas, el tablero lo dice claramente', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByText('No hay facturas todavía.')).toBeVisible();
});
