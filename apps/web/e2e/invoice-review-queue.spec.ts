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
  await page.route(`${API}/families`, async (route) => {
    await route.fulfill({
      json: [
        {
          id: PENDING_INVOICE.family_id,
          name: 'Familia Garcia',
          address: null,
          status: 'active',
        },
        {
          id: PAID_INVOICE.family_id,
          name: 'Familia Lopez',
          address: null,
          status: 'active',
        },
      ],
    });
  });
});

test('staff ve las facturas organizadas en un tablero por estado', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [PENDING_INVOICE, PAID_INVOICE] });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByRole('heading', { name: 'Cola de revisión' })).toBeVisible();
  await expect(page.getByLabel('Filtrar por familia')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Pendiente de revisión' })).toBeVisible();
  // Cada tarjeta lleva dentro un <select> con TODAS las familias, asi que
  // buscar por el nombre de la familia casa con todas las tarjetas. La etiqueta
  // del selector de familia si es unica por tarjeta.
  await expect(page.getByLabel('Asignar familia de la factura de Familia Garcia')).toBeVisible();
  await expect(page.getByText('35% confianza')).toBeVisible();
  await expect(page.getByLabel('Asignar familia de la factura de Familia Lopez')).toBeVisible();
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

test('staff puede asignar una familia a una factura sin enlazar', async ({ page }) => {
  const unlinked = { ...PENDING_INVOICE, family_id: null, family_name: null };
  let patchedBody: Record<string, unknown> | null = null;
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [unlinked] });
  });
  await page.route(`${API}/family-invoices/${unlinked.id}`, async (route) => {
    patchedBody = JSON.parse(route.request().postData() ?? '{}');
    await route.fulfill({
      json: { ...unlinked, family_id: patchedBody.family_id, family_name: 'Familia Garcia' },
    });
  });

  await page.goto('/dashboard/invoices');
  await page
    .getByLabel('Asignar familia de la factura de sin asignar')
    .selectOption(PENDING_INVOICE.family_id as string);

  await expect.poll(() => patchedBody?.family_id).toBe(PENDING_INVOICE.family_id);
});

test('sin facturas, el tablero lo dice claramente', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/dashboard/invoices');

  await expect(page.getByText('No hay facturas todavía.')).toBeVisible();
});

test('staff puede publicar varias facturas a la vez', async ({ page }) => {
  let bulkBody: Record<string, unknown> | null = null;
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [PENDING_INVOICE] });
  });
  await page.route(`${API}/family-invoices/bulk`, async (route) => {
    bulkBody = JSON.parse(route.request().postData() ?? '{}');
    await route.fulfill({ json: { updated: 1, failed: [] } });
  });

  await page.goto('/dashboard/invoices');
  await page.getByLabel('Seleccionar factura de Familia Garcia').check();
  await expect(page.getByText('1 seleccionada(s)')).toBeVisible();
  await page.getByRole('button', { name: 'Publicar' }).click();

  await expect
    .poll(() => bulkBody)
    .toEqual({
      ids: [PENDING_INVOICE.id],
      status: 'sent',
    });
});

// TASK-0127/TASK-0128: hasta ahora no habia ningun sitio en toda la interfaz
// donde corregir lo que el extractor sacaba mal. Solo se podia publicar el
// error o dejar la factura en la cola para siempre.
const INCOMPLETE_INVOICE = {
  ...PENDING_INVOICE,
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  amount: null,
  issue_date: null,
  confidence: 0,
};

test('staff corrige el importe y la fecha de una factura mal extraida', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [INCOMPLETE_INVOICE] });
  });

  let patched: Record<string, unknown> | null = null;
  await page.route(`${API}/family-invoices/${INCOMPLETE_INVOICE.id}`, async (route) => {
    patched = route.request().postDataJSON();
    await route.fulfill({ json: { ...INCOMPLETE_INVOICE, ...patched } });
  });

  await page.goto('/dashboard/invoices');
  await expect(page.getByText('Faltan datos')).toBeVisible();

  await page
    .getByRole('button', {
      name: `Corregir datos de la factura de ${INCOMPLETE_INVOICE.family_name}`,
      exact: true,
    })
    .click();
  await page.getByLabel('Importe').fill('121.00');
  await page.getByLabel('Fecha de emisión').fill('2026-09-05');
  await page.getByRole('button', { name: 'Guardar', exact: true }).click();

  await expect(page.getByText('Factura corregida')).toBeVisible();
  expect(patched).toMatchObject({ amount: '121.00', issue_date: '2026-09-05' });
  await expect(page.getByText(/121,00/)).toBeVisible();
});

test('no se publica una factura sin importe y se dice por que', async ({ page }) => {
  await page.route(`${API}/family-invoices`, async (route) => {
    await route.fulfill({ json: [INCOMPLETE_INVOICE] });
  });

  await page.goto('/dashboard/invoices');
  await page
    .getByLabel(`Cambiar estado de la factura de ${INCOMPLETE_INVOICE.family_name}`)
    .selectOption('sent');

  await expect(page.getByText(/Indica el importe antes de publicar/)).toBeVisible();
});
