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
│  Landing · login · facturas (padre) · cola revisión (staff)  │
└─────────────────────────────┬─────────────────────────────────┘
                              │ HTTP / JSON
┌─────────────────────────────▼─────────────────────────────────┐
│                  FastAPI (apps/api) ✅                        │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Health ✅   │  │ Auth ✅      │  │ Familias/Alumnos ✅ │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Ingesta 🧪  │  │ Facturación 🧪│  │ Proveedores ✅     │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
└─────────────┬───────────────────────┬─────────────────────────┘
              │ SQLAlchemy ✅          │ Celery/RQ ⏳
     ┌────────▼────────┐     ┌────────▼────────┐
     │   PostgreSQL    │     │  Redis + cola   │
     └─────────────────┘     └────────┬────────┘
                                      │
                             ┌────────▼────────┐    ┌──────────────────────┐
                             │    Mailpit      │← dev│ Gmail API 🧪          │
                             │ (SMTP real luego)│    │ (FakeGmailClient hoy)│
                             └─────────────────┘    └──────────────────────┘
```

🧪 = construido y con tests en verde, pero contra credenciales/datos
**simulados** (decisión 2026-08-25 del usuario) — no verificado todavía
contra Gmail real ni facturas reales.

---

## Estado por componente

| Carpeta                | Contenido                                                                                                                                                     | Estado                                                             |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `apps/api`             | FastAPI, módulo health (`GET /health`), CORS, `API_PORT` por env                                                                                              | ✅ Operativo                                                       |
| Persistencia (Fase 1)  | SQLAlchemy + Alembic; modelos User/Family/Student/Contract + migración inicial (verificada contra SQLite; falta aplicarla contra Postgres real, TASK-0009)    | ✅ Operativo (Postgres real pendiente)                             |
| Auth y CRUD            | JWT + bcrypt; `POST /auth/login`, `GET /auth/me`; CRUD `families`/`students`/`contracts`/`users` con invariante `familyId` (RULE-005)                         | ✅ Operativo                                                       |
| Frontend               | `/login`, `/dashboard` (facturas propias si `parent`), `/dashboard/invoices` (cola de revisión), `/dashboard/families` (+ficha con alumnos/notas/tareas/RGPD) | ✅ Operativo (falta editar alumno y CRUD de `Contract`, TASK-0039) |
| Persistencia (Fase 2)  | Modelos Supplier/Email/Document/FamilyInvoice/SupplierInvoice/AuditLog + 3 migraciones más (nullable/email)                                                   | ✅ Operativo (Postgres real pendiente)                             |
| Ingesta (`ingestion/`) | `GmailClient`/`FakeGmailClient`, orquestador, zip-bomb, clasificación, extracción por plantilla, matching automático a `Family`                               | 🧪 Simulada — sin Gmail/PDF reales todavía                         |
| Cola de revisión       | `family-invoices`/`supplier-invoices`: listado por confianza, detalle, corrección con audit trail                                                             | ✅ Operativo                                                       |
| Notas y tareas         | `Note` (staff, por Family/Student) y `Task` (recordatorios vinculados a una familia)                                                                          | ✅ Operativo                                                       |
| Notificaciones         | `EmailSender`/`NoOpEmailSender`/`SmtpEmailSender`; avisa a la familia al enlazar una factura                                                                  | 🧪 Simulada — sin Mailpit real todavía                             |
| RGPD                   | `GET /families/{id}/export`, `POST /families/{id}/anonymize` — mecanismo listo, política de retención sin decidir (TASK-0012)                                 | ✅ Mecanismo operativo                                             |
| Cola de trabajo        | Redis + Celery/RQ; hoy el orquestador corre síncrono, sin cola                                                                                                | ⏳ Fase posterior (no bloquea la ingesta simulada)                 |
| CI (`ci.yml`)          | JS: format → lint → build → test → e2e. API: format → lint → test                                                                                             | ✅ Operativo                                                       |

---

## Invariante de acceso por familia

No hay multi-tenant (una sola empresa), pero sí un invariante equivalente,
**implementado y probado** desde TASK-0018 (`tests/test_family_scoping.py`):

- Un `User` con `role = parent` tiene un `familyId` fijo.
- Todo endpoint de negocio filtra **obligatoriamente** por ese `familyId`
  cuando quien pregunta es un padre — `dependencies.ensure_family_access()`
  para lecturas por id, filtro forzado en las queries de listado (el padre no
  puede pedir el `family_id` de otra familia ni por query param).
- Acceso denegado a un padre → `404`, no `403` (no confirma si el recurso
  de otra familia existe).
- `role = staff` / `admin` son los únicos con acceso transversal (todas las
  familias, y las `SupplierInvoice`, que un padre nunca ve) — además son los
  únicos que pueden escribir (`POST`/`PATCH`) en `families`/`students`/`contracts`/`users`.
- Invariante nº 1 del proyecto: RULE-005 de [AGENTS.md](../AGENTS.md).

---

## Estructura del monorepo

```
apps/api/
  pyproject.toml           # uv, deps: fastapi, sqlalchemy, alembic, pyjwt, bcrypt...
  alembic/                 # migraciones (target_metadata = Base.metadata)
  src/
    main.py                # bootstrap FastAPI + CORS + routers
    config.py               # Settings (pydantic-settings)
    db.py                    # engine, Session, Base, get_db
    security.py              # hash_password, JWT encode/decode
    dependencies.py          # get_current_user, require_role, ensure_family_access
    audit.py                 # record_field_changes (RULE-009/TASK-0026)
    models/                  # User/Family/Student/Contract + Supplier/Email/Document/
                              # FamilyInvoice/SupplierInvoice/AuditLog + Note/Task
    schemas/                 # Pydantic: uno por modelo de negocio
    routers/                 # health, auth, users, families (+export/anonymize), students,
                              # contracts, family_invoices, supplier_invoices, notes, tasks
    ingestion/                # gmail_client (protocol) + fake_gmail_client, safe_zip,
                              # scanning (NoOp/Clamd), classification, extraction, matching, pipeline
    notifications/            # email_sender (NoOp/Smtp), service (compone y envía avisos)
  tests/                    # pytest: unit + integracion (TestClient + SQLite)
apps/web/
  src/app/                  # App Router: /, /login, /dashboard (facturas propias),
                              # /dashboard/invoices (cola de revisión),
                              # /dashboard/families(+[id]) (ficha: alumnos, notas, tareas, RGPD)
  src/lib/                  # api.ts (cliente HTTP), auth-storage.ts, auth-context.tsx
  e2e/                      # specs Playwright (mockean la API con page.route,
                              # ancladas al origen de la API — ver nota en ISSUES.md TASK-0036)
  playwright.config.ts      # next start en :4123 tras build
```

Módulos frontend planificados (Fase 3+): editar un alumno existente, CRUD
de `Contract`, descarga real (fichero) del export RGPD (TASK-0039/0040).

---

## Estrategia de pruebas

| Capa        | Herramientas                           | Qué cubre                                                                                                                             |
| ----------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Unitaria    | pytest (api)                           | Lógica pura: hashing, JWT, validaciones                                                                                               |
| Integración | pytest + `TestClient` (httpx) + SQLite | Capa HTTP completa: auth, CRUD, invariante `familyId`, pipeline de ingesta con `FakeGmailClient`, notificaciones, RGPD (85 tests api) |
| E2E         | Playwright (chromium)                  | Landing, login, facturas propias, cola de revisión y gestión de familias servidos por `next start`, API mockeada (8 tests web)        |

- **E2E contra producción**: igual que en MailForge, Playwright arranca
  `next start` en `127.0.0.1:4123` (puerto dedicado, host explícito). Las
  llamadas a la API se mockean con `page.route()` (sin API real corriendo).
- **Integración con SQLite, no con mocks del ORM**: cada test crea su propia
  base SQLite en memoria (`StaticPool`, `check_same_thread=False`) y ejercita
  modelos + endpoints reales vía `TestClient`. Postgres real sigue pendiente
  (TASK-0009).
- **Ingesta con doble de prueba, no con mocks de función suelta**:
  `FakeGmailClient` implementa el mismo protocolo `GmailClient` que usaría un
  cliente OAuth real — decide "nuevo" por etiqueta, igual que Gmail de
  verdad. Esto evitó un bug real: una primera versión marcaba "visto" al leer
  el mensaje en vez de al etiquetarlo, y el test de idempotencia lo detectó.

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

| Variable                         | Usada por      | Desde                                      | Por defecto                                                  |
| -------------------------------- | -------------- | ------------------------------------------ | ------------------------------------------------------------ |
| API_PORT                         | apps/api       | ahora                                      | 8000                                                         |
| CORS_ORIGIN                      | apps/api       | ahora                                      | http://localhost:3000                                        |
| NEXT_PUBLIC_API_URL              | apps/web       | reservada                                  | http://localhost:8000                                        |
| E2E_PORT                         | apps/web (E2E) | opcional                                   | 4123                                                         |
| DATABASE_URL                     | apps/api       | ahora (Postgres real pendiente, TASK-0009) | postgresql+psycopg://crm:crm@localhost:5432/crm_transporte   |
| REDIS_URL                        | apps/api       | Fase 2                                     | -                                                            |
| JWT_SECRET / JWT_EXPIRES_MINUTES | apps/api       | ahora                                      | valor de desarrollo — RULE-006: cambiar en todo entorno real |
| GMAIL_*                          | apps/api       | Fase 2                                     | -                                                            |
| SMTP_*                           | apps/api       | Fase 4                                     | Mailpit en desarrollo                                        |

Referencia canónica: `.env.example` en la raíz.

---

## Decisiones importantes de diseño

### ¿Por qué simular Gmail en vez de esperar credenciales reales?

Decisión explícita del usuario (2026-08-25): el `GmailClient` es un
protocolo (puerto/adaptador); `FakeGmailClient` lo implementa en memoria.
El orquestador (`ingestion/pipeline.py`) no sabe ni le importa cuál de los
dos usa. Cuando lleguen credenciales reales (TASK-0032), se añade un
`RealGmailClient` con `google-api-python-client` y se cambia una línea de
wiring — cero cambios en la lógica ya probada.

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
