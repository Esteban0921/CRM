import { test, expect } from '@playwright/test';

test('un padre inicia sesión y ve su dashboard', async ({ page }) => {
  await page.route('**/auth/login', async (route) => {
    await route.fulfill({
      json: { access_token: 'fake-token', token_type: 'bearer' },
    });
  });
  await page.route('**/auth/me', async (route) => {
    await route.fulfill({
      json: {
        id: '11111111-1111-1111-1111-111111111111',
        email: 'padre@example.com',
        name: 'Ana Padre',
        role: 'parent',
        family_id: '22222222-2222-2222-2222-222222222222',
      },
    });
  });
  await page.route('**/family-invoices', async (route) => {
    await route.fulfill({
      json: [
        {
          id: '33333333-3333-3333-3333-333333333333',
          document_id: '44444444-4444-4444-4444-444444444444',
          family_id: '22222222-2222-2222-2222-222222222222',
          student_id: null,
          contract_id: null,
          amount: '45.00',
          currency: 'EUR',
          issue_date: '2026-09-01',
          due_date: null,
          status: 'sent',
          extracted_data: null,
          confidence: 0.9,
        },
      ],
    });
  });

  await page.goto('/login');
  await page.getByLabel('Email').fill('padre@example.com');
  await page.getByLabel('Contraseña').fill('claveSegura123');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole('heading', { name: 'Hola, Ana Padre' })).toBeVisible();
  await expect(page.getByText('Facturas de tu familia')).toBeVisible();
  await expect(page.getByText(/45,00/)).toBeVisible();
});

test('un fallo de login muestra el mensaje de error', async ({ page }) => {
  await page.route('**/auth/login', async (route) => {
    await route.fulfill({ status: 401, json: { detail: 'Email o contrasena incorrectos' } });
  });

  await page.goto('/login');
  await page.getByLabel('Email').fill('padre@example.com');
  await page.getByLabel('Contraseña').fill('incorrecta');
  await page.getByRole('button', { name: 'Entrar' }).click();

  // Next.js expone su propio role="alert" (route announcer); nos ceñimos al texto.
  await expect(page.getByText('Email o contrasena incorrectos')).toBeVisible();
});

test('sin sesión, el dashboard redirige a login', async ({ page }) => {
  await page.goto('/dashboard');

  await expect(page).toHaveURL(/\/login/);
});
