# Arquitectura de CRM Transporte

CRM interno (una sola empresa, sin multi-tenant) para una empresa de
transporte escolar: gestiona familias, alumnos, contratos y la facturación
asociada. La ingesta automática de facturas por Gmail —descrita en detalle en
[SPEC_ORIGINAL.md](SPEC_ORIGINAL.md)— es un módulo dentro de este CRM.

Este documento marca qué está implementado (✅) y qué queda planificado (⏳).
El trabajo vivo está en [ISSUES.md](../ISSUES.md).

---

## Visión general

```
┌─────────────────────────────────────────────────────────────┐
│                  Next.js (apps/web) ✅                       │
│  Landing operativa · dashboard padre / panel staff (Fase 1+) │
└─────────────────────────────┬─────────────────────────────────┘
                              │ HTTP / JSON
┌─────────────────────────────▼─────────────────────────────────┐
│                  FastAPI (apps/api) ✅                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Health ✅   │  │ Auth ⏳      │  │ Familias/Alumnos ⏳ │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Ingesta ⏳  │  │ Facturación ⏳│  │ Proveedores ⏳     │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────┬───────────────────────┬─────────────────────────┘
              │ SQLAlchemy ⏳          │ Celery/RQ ⏳
     ┌────────▼────────┐     ┌────────▼────────┐
     │   PostgreSQL    │     │  Redis + cola   │
     └─────────────────┘     └────────┬────────┘
                                      │
                             ┌────────▼────────┐         ┌─────────────┐
                             │    Mailpit      │ ← dev    │  Gmail API  │
                             │ (SMTP real luego)│         │  (ingesta) ⏳│
                             └─────────────────┘         └─────────────┘
```

---

## Estado por componente

| Carpeta       | Contenido                                                                                                                                                  | Estado       |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `apps/api`    | FastAPI, módulo health (`GET /health`), CORS, `API_PORT` por env                                                                                           | ✅ Operativo |
| `apps/web`    | Next.js 15 App Router, Tailwind v4 CSS-first, landing estática                                                                                             | ✅ Operativo |
| Persistencia  | SQLAlchemy + Alembic; modelos User/Family/Student/Contract + migración inicial (verificada contra SQLite; falta aplicarla contra Postgres real, TASK-0009) | 🔧 Fase 1    |
| Auth          | JWT (pyjwt) + bcrypt; `POST /auth/login`. Falta guard `familyId` y CRUD (TASK-0018)                                                                        | 🔧 Fase 1    |
| Cola          | Redis + Celery/RQ; ingesta de Gmail                                                                                                                        | 🔧 Fase 2    |
| CI (`ci.yml`) | JS: format → lint → build → test → e2e. API: format → lint → test                                                                                          | ✅ Operativo |

---

## Invariante de acceso por familia

No hay multi-tenant (una sola empresa), pero sí un invariante equivalente:

- Un `User` con `role = parent` tiene un `familyId` fijo.
- Todo endpoint de negocio que devuelva datos de facturación filtra
  **obligatoriamente** por ese `familyId` cuando quien pregunta es un padre.
- `role = staff` / `admin` son los únicos con acceso transversal (todas las
  familias, y las `SupplierInvoice`, que un padre nunca ve).
- En FastAPI: una dependencia (`Depends`) que resuelve el usuario autenticado
  y expone su `familyId`; los routers de negocio la usan siempre (Fase 1).
- Invariante nº 1 del proyecto: RULE-005 de [AGENTS.md](../AGENTS.md).

---

## Estructura del monorepo

```
apps/api/
  pyproject.toml           # uv, deps: fastapi, uvicorn, pydantic-settings
  src/
    main.py                # bootstrap FastAPI + CORS
    config.py               # Settings (pydantic-settings)
    routers/health.py
  tests/test_health.py      # pytest + TestClient
apps/web/
  src/app/                  # App Router: layout, page, globals.css
  e2e/                      # specs Playwright
  playwright.config.ts      # next start en :4123 tras build
```

Módulos backend planificados (Fase 1+): auth, families, students, contracts,
suppliers, ingestion, invoices, notifications.

---

## Estrategia de pruebas

| Capa        | Herramientas                  | Qué cubre                                             |
| ----------- | ----------------------------- | ----------------------------------------------------- |
| Unitaria    | pytest (api)                  | Lógica pura: validaciones, servicios con mocks        |
| Integración | pytest + `TestClient` (httpx) | Capa HTTP completa contra `/health` y futuros routers |
| E2E         | Playwright (chromium)         | La landing/dashboard servida por `next start`         |

- **E2E contra producción**: igual que en MailForge, Playwright arranca
  `next start` en `127.0.0.1:4123` (puerto dedicado, host explícito).
- **Sin base de datos todavía**: ninguna prueba depende de Postgres/Redis;
  llegan en Fase 1+ con sus propias pruebas (fixtures, no mocks, para la
  extracción de PDF/XML — ver RULE-008).

---

## Tooling de calidad

| Pieza               | Cómo funciona                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| ESLint 9 + Prettier | Igual convención que MailForge; `apps/api` excluido (no es JS).                                  |
| ruff                | Formato + lint del lado Python (`apps/api`); sustituye a black/isort/flake8.                     |
| Husky + lint-staged | Un solo hook de pre-commit para ambos stacks: prettier/eslint en JS, ruff en `apps/api/**/*.py`. |
| Turborepo           | Orquesta solo el lado JS (`apps/web`); el lado Python se gestiona con `uv` directamente.         |
| GitHub Actions      | Un job: gates JS completos, luego `uv sync` + ruff + pytest para la API.                         |

---

## Variables de entorno

| Variable                    | Usada por      | Desde     | Por defecto           |
| --------------------------- | -------------- | --------- | --------------------- |
| API_PORT                    | apps/api       | ahora     | 8000                  |
| CORS_ORIGIN                 | apps/api       | ahora     | http://localhost:3000 |
| NEXT_PUBLIC_API_URL         | apps/web       | reservada | http://localhost:8000 |
| E2E_PORT                    | apps/web (E2E) | opcional  | 4123                  |
| DATABASE_URL                | apps/api       | Fase 1    | -                     |
| REDIS_URL                   | apps/api       | Fase 2    | -                     |
| JWT_SECRET / JWT_EXPIRES_IN | apps/api       | Fase 1    | -                     |
| GMAIL_*                     | apps/api       | Fase 2    | -                     |
| SMTP_*                      | apps/api       | Fase 4    | Mailpit en desarrollo |

Referencia canónica: `.env.example` en la raíz.

---

## Decisiones importantes de diseño

### ¿Por qué FastAPI y no NestJS (como en MailForge)?

Stack Python elegido deliberadamente por el ecosistema de parsing de
PDF/XML (pypdf, pdfplumber, lxml), pieza central del módulo de ingesta.
Implica mantener dos stacks de backend en el equipo; se acepta el coste por
la ventaja concreta en esta pieza.

### ¿Por qué separar `FamilyInvoice` de `SupplierInvoice` en vez de una tabla `Invoice` polimórfica?

Tienen ciclos de vida y visibilidad distintos: una la ve el padre en el
dashboard, la otra es solo interna. Separarlas evita columnas nulas a medias
y guards de autorización más frágiles ("¿esta fila es visible para un padre?").

### ¿Por qué uv en vez de Poetry/pip?

Más rápido, un único binario, lockfile reproducible; es el estándar de facto
en proyectos Python nuevos a esta fecha.

### Autenticación (Fase 1)

JWT propio (access + refresh), un solo `User` con `role` en vez de tablas
separadas por rol — mismo patrón de auth para padres y staff, distinto solo
en autorización.

---

## Seguridad desde el principio

- Todas las rutas de negocio requieren autenticación.
- Todo query de facturación filtra por `familyId` cuando el rol es `parent` (RULE-005).
- Ningún adjunto descargado de Gmail se procesa sin pasar antes por escaneo
  antivirus y límites de tamaño/descompresión (protección zip-bomb) — Fase 2,
  no diferible.
- Validación de entrada con Pydantic en todos los endpoints.
- Datos de menores (`Student`): tratamiento acorde a RGPD — política de
  retención y derecho de acceso/supresión se deciden antes de Fase 3
  (ver ROADMAP.md Fase 4).
