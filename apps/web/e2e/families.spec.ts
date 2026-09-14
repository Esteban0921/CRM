import { test, expect } from '@playwright/test';

// Importante: las rutas mockeadas se anclan al origen de la API
// (http://localhost:8000), no a "**/families" — un patrón así de amplio
// también intercepta la propia navegación de la página en :4123, que
// termina en la misma ruta "/dashboard/families/{id}".
const API = 'http://localhost:8000';

const STAFF_ME = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'staff@example.com',
  name: 'Equipo',
  role: 'staff',
  family_id: null,
};

const FAMILY = {
  id: '22222222-2222-2222-2222-222222222222',
  name: 'Familia Garcia',
  address: 'Calle Falsa 123',
  status: 'active',
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => window.localStorage.setItem('crm_access_token', 'fake-token'));
  await page.route(`${API}/auth/me`, async (route) => {
    await route.fulfill({ json: STAFF_ME });
  });
});

test('staff ve el listado de familias y crea una nueva', async ({ page }) => {
  let created = false;
  await page.route(`${API}/families`, async (route) => {
    if (route.request().method() === 'POST') {
      created = true;
      await route.fulfill({
        status: 201,
        json: { ...FAMILY, id: '33333333-3333-3333-3333-333333333333', name: 'Familia Nueva' },
      });
      return;
    }
    await route.fulfill({
      json: created ? [FAMILY, { ...FAMILY, name: 'Familia Nueva' }] : [FAMILY],
    });
  });

  await page.goto('/dashboard/families');

  await expect(page.getByText('Familia Garcia')).toBeVisible();

  await page.getByRole('button', { name: 'Nueva familia' }).click();
  await page.getByLabel('Nombre').fill('Familia Nueva');
  await page.getByRole('button', { name: 'Añadir familia' }).click();

  await expect(page.getByText('Familia Nueva')).toBeVisible();
});

test('staff abre una familia, añade una nota y una tarea', async ({ page }) => {
  const notes: unknown[] = [];
  const tasks: unknown[] = [];

  await page.route(`${API}/families/${FAMILY.id}`, async (route) => {
    await route.fulfill({ json: FAMILY });
  });
  await page.route(`${API}/students*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/notes*`, async (route) => {
    if (route.request().method() === 'POST') {
      notes.push({ id: 'n1', body: 'Recoge sola los viernes' });
      await route.fulfill({ status: 201, json: notes[0] });
      return;
    }
    await route.fulfill({ json: notes });
  });
  await page.route(`${API}/contracts*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/tasks*`, async (route) => {
    if (route.request().method() === 'POST') {
      tasks.push({
        id: 't1',
        family_id: FAMILY.id,
        title: 'Contactar por impago',
        status: 'pending',
      });
      await route.fulfill({ status: 201, json: tasks[0] });
      return;
    }
    await route.fulfill({ json: tasks });
  });

  await page.goto(`/dashboard/families/${FAMILY.id}`);

  await expect(page.getByRole('heading', { name: 'Familia Garcia' })).toBeVisible();

  await page.getByPlaceholder('Nueva nota').fill('Recoge sola los viernes');
  await page.getByRole('button', { name: 'Añadir nota' }).click();
  await expect(page.getByText('Recoge sola los viernes')).toBeVisible();

  await page.getByPlaceholder('Nueva tarea').fill('Contactar por impago');
  await page.getByRole('button', { name: 'Añadir tarea' }).click();
  await expect(page.getByText('Contactar por impago')).toBeVisible();
});

test('staff descarga el export RGPD como fichero y no usa alert', async ({ page }) => {
  await page.route(`${API}/families/${FAMILY.id}`, async (route) => {
    await route.fulfill({ json: FAMILY });
  });
  await page.route(`${API}/students*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/contracts*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/notes*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/tasks*`, async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route(`${API}/families/${FAMILY.id}/export`, async (route) => {
    await route.fulfill({ json: { family: FAMILY, students: [] } });
  });

  const alerts: string[] = [];
  page.on('dialog', (dialog) => {
    alerts.push(dialog.message());
    return dialog.dismiss();
  });

  await page.goto(`/dashboard/families/${FAMILY.id}`);
  await page.getByRole('button', { name: 'Exportar datos (RGPD)' }).click();

  await expect(page.getByText('Exportación descargada')).toBeVisible();
  expect(alerts).toEqual([]);
});
