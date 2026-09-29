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
│  Landing · login · dashboards padre/staff · kanban · familias │
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
                             │  Mailpit ✅     │← dev│ Gmail API 🧪          │
                             │ (SMTP real, dev) │    │ (FakeGmailClient hoy)│
                             └─────────────────┘    └──────────────────────┘
```

🧪 = construido y con tests en verde, pero contra credenciales/datos
**simulados** (decisión 2026-08-25 del usuario) — hoy solo Gmail y la
extracción de texto de PDF siguen así (TASK-0032/TASK-0031); el resto de
piezas que empezaron simuladas (ClamAV, SMTP/Mailpit, Postgres real) ya se
verificaron contra servicios reales el 2026-08-26.

---

## Estado por componente

| Carpeta                | Contenido                                                                                                                                                                                                                                                                   | Estado                                                                                           |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `apps/api`             | FastAPI, módulo health (`GET /health` hace `SELECT 1`; 503 si la DB no responde), CORS, `API_PORT` por env                                                                                                                                                                  | ✅ Operativo                                                                                     |
| Persistencia (Fase 1)  | SQLAlchemy + Alembic; modelos User/Family/Student/Contract + migración inicial (verificada contra SQLite y, desde TASK-0009, contra Postgres real)                                                                                                                          | ✅ Operativo, verificado contra Postgres real                                                    |
| Auth y CRUD            | JWT + bcrypt; `POST /auth/login`, `GET /auth/me`; CRUD `families`/`students`/`contracts`/`users` con invariante `familyId` (RULE-005)                                                                                                                                       | ✅ Operativo                                                                                     |
| Frontend               | `/dashboard` (padre: «He pagado»; staff: cockpit + huecos del mes), `/dashboard/search`, `/dashboard/invoices` (kanban + acciones masivas), `/dashboard/tasks`, `/dashboard/credit-notes`, `/dashboard/families`, `/dashboard/suppliers`; campana de avisos y paleta Ctrl+K | ✅ Operativo                                                                                     |
| Persistencia (Fase 2)  | Modelos Supplier/Email/Document/FamilyInvoice/SupplierInvoice/AuditLog + 3 migraciones más (nullable/email)                                                                                                                                                                 | ✅ Operativo, verificado contra Postgres real                                                    |
| Ingesta (`ingestion/`) | `GmailClient`/`FakeGmailClient`, orquestador, zip-bomb, clasificación, extracción por plantilla, matching automático a `Family`; escaneo con `ClamdScanner` real; `POST /ingestion/run` (staff/admin) como punto de entrada real (TASK-0041)                                | 🧪 Parcial — Gmail y extracción de PDF simulados (TASK-0032/0031); antivirus ya real (TASK-0033) |
| Cola de revisión       | `family-invoices`/`supplier-invoices`: listado por confianza, detalle, corrección con audit trail                                                                                                                                                                           | ✅ Operativo                                                                                     |
| Notas y tareas         | `Note` (staff, por Family/Student) y `Task` (recordatorios vinculados a una familia)                                                                                                                                                                                        | ✅ Operativo                                                                                     |
| Notificaciones         | `EmailSender`/`NoOpEmailSender`/`SmtpEmailSender`; avisa al publicar, al vencer y a 7 días; campana staff `GET /notifications/inbox` (TASK-0066)                                                                                                                            | ✅ Operativo, verificado contra Mailpit real (TASK-0034)                                         |
| RGPD                   | `GET /families/{id}/export`, `POST /families/{id}/anonymize` — mecanismo listo, política de retención sin decidir (TASK-0012)                                                                                                                                               | ✅ Mecanismo operativo                                                                           |
| Cola de trabajo        | Redis + Celery/RQ; hoy el orquestador corre síncrono, sin cola                                                                                                                                                                                                              | ⏳ Fase posterior (no bloquea la ingesta simulada)                                               |
| CI (`ci.yml`)          | JS: format → lint → build → test → e2e. API: format → lint → test                                                                                                                                                                                                           | ✅ Operativo                                                                                     |

---

## Invariante de acceso por familia

No hay multi-tenant (una sola empresa), pero sí un invariante equivalente,
**implementado y probado** desde TASK-0018 (`tests/test_family_scoping.py`):

- Un `User` con `role = parent` tiene un `familyId` fijo.
- Todo endpoint de negocio filtra **obligatoriamente** por ese `familyId`
  cuando quien pregunta es un padre — `dependencies.ensure_family_access()`
  para lecturas por id, filtro forzado en las queries de listado (el padre no
  puede pedir el `family_id` de otra familia ni por query param). Un recurso
  sin `familyId` (factura aún sin enlazar) tampoco es del padre.
- Un padre **nunca** ve `FamilyInvoice` en `pending_review` (RULE-017): el
  dato extraído no se publica a la familia hasta que staff lo revisa.
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
                              # FamilyInvoice/Payment/SupplierInvoice/AuditLog + Note/Task
    schemas/                 # Pydantic: uno por modelo de negocio
    routers/                 # health, auth, users, families (+export/anonymize/billing/activity,
                              # snapshot de cobro en el listado),
                              # students, contracts, family_invoices (+export.csv, /bulk, /claim-payment,
                              # /confirm-payment, /payments), notes, tasks, ingestion, documents,
                              # billing (+summary/at-risk/unbilled/month-report),
                              # notifications (+inbox, overdue/due-soon reminders), search, emails
    ingestion/                # gmail_client (protocol) + fake_gmail_client, safe_zip,
                              # scanning (NoOp/Clamd), classification, extraction, matching, pipeline
    notifications/            # email_sender (NoOp/Smtp), service (compone y envía avisos)
  tests/                    # pytest: unit + integracion (TestClient + SQLite)
apps/web/
  src/app/                  # App Router: /, /login, /dashboard,
                              # /dashboard/invoices, /dashboard/suppliers,
                              # /dashboard/families(+[id])
  src/components/           # sistema de diseño propio (ui + shell)
  src/lib/                  # api.ts (cliente HTTP, 401 → login), auth-storage.ts, auth-context.tsx
  e2e/                      # specs Playwright (mockean la API con page.route,
                              # ancladas al origen de la API — ver nota en ISSUES.md TASK-0036)
  playwright.config.ts      # next start en :4123 tras build
```

Módulos frontend aún fuera: Gmail OAuth y extracción real de PDF (TASK-0032/0031).

---

## Estrategia de pruebas

| Capa        | Herramientas                           | Qué cubre                                                                                                                     |
| ----------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Unitaria    | pytest (api)                           | Lógica pura: hashing, JWT, validaciones                                                                                       |
| Integración | pytest + `TestClient` (httpx) + SQLite | Capa HTTP completa: auth, CRUD, invariante `familyId`, pipeline de ingesta con `FakeGmailClient`, notificaciones, RGPD        |
| E2E         | Playwright (chromium)                  | Landing, login, facturas propias, tablero kanban y gestión de familias servidos por `next start`, API mockeada (12 tests web) |

- **E2E contra producción**: igual que en MailForge, Playwright arranca
  `next start` en `127.0.0.1:4123` (puerto dedicado, host explícito). Las
  llamadas a la API se mockean con `page.route()` (sin API real corriendo).
  Gotcha (TASK-0042): el preview de desarrollo (`pnpm dev`) y `next build`
  comparten `.next` — no correr ambos a la vez.
- **Integración con SQLite, no con mocks del ORM**: cada test crea su propia
  base SQLite en memoria (`StaticPool`, `check_same_thread=False`) y ejercita
  modelos + endpoints reales vía `TestClient`. Verificado además contra
  Postgres real (TASK-0009).
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

| Variable                                                                     | Usada por      | Desde                                              | Por defecto                                                                             |
| ---------------------------------------------------------------------------- | -------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------- |
| APP_ENV                                                                      | apps/api       | ahora (TASK-0088)                                  | development — con `production` el arranque exige JWT_SECRET propio                      |
| API_PORT                                                                     | apps/api       | declarada, sin efecto (TASK-0174)                  | 8000 — el puerto lo fija el CLI de uvicorn                                              |
| CORS_ORIGINS                                                                 | apps/api       | ahora (TASK-0141)                                  | http://localhost:3000,http://127.0.0.1:3000                                             |
| CORS_ORIGIN                                                                  | apps/api       | heredada, se fusiona con CORS_ORIGINS              | vacia                                                                                   |
| NEXT_PUBLIC_API_URL                                                          | apps/web       | ahora — la usa `src/lib/api.ts` en cada peticion   | http://localhost:8000                                                                   |
| E2E_PORT                                                                     | apps/web (E2E) | opcional                                           | 4123                                                                                    |
| DATABASE_URL                                                                 | apps/api       | ahora, verificado contra Postgres real (TASK-0009) | postgresql+psycopg://crm:crm@127.0.0.1:5432/crm_transporte — no `localhost` (TASK-0181) |
| REDIS_URL                                                                    | apps/api       | declarada, sin uso en el codigo (TASK-0174)        | -                                                                                       |
| JWT_SECRET / JWT_EXPIRES_MINUTES                                             | apps/api       | ahora                                              | valor de desarrollo — con APP_ENV=production el arranque falla si no se cambia          |
| LOGIN_MAX_ATTEMPTS / LOGIN_ATTEMPT_WINDOW_SECONDS                            | apps/api       | ahora (TASK-0094)                                  | 10 intentos / 300 s por (IP, email)                                                     |
| GMAIL_*                                                                      | apps/api       | Fase 2                                             | -                                                                                       |
| SMTP_*                                                                       | apps/api       | Fase 4, verificado contra Mailpit real (TASK-0034) | Mailpit en desarrollo (127.0.0.1:1025)                                                  |
| CLAMAV host/port (`ClamdScanner`)                                            | apps/api       | Fase 2, verificado contra ClamAV real (TASK-0033)  | 127.0.0.1:3310 (servicio `clamav` en docker-compose.yml)                                |
| ATTACHMENTS_DIR                                                              | apps/api       | Fase 2 (TASK-0041)                                 | ./data/attachments (gitignored)                                                         |
| MAX_ATTACHMENT_BYTES / MAX_ATTACHMENTS_PER_EMAIL / MAX_EXTRACTION_TEXT_BYTES | apps/api       | ahora (TASK-0090, RULE-016)                        | 10 MB / 20 / 256 KB                                                                     |

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

JWT propio (access token, 15 min). Un solo `User` con `role` en vez de tablas
separadas por rol — mismo patrón de auth para padres y staff, distinto solo
en autorización. Refresh token y cookies httpOnly se posponen a hosting real
(documentado en [rules_and_invariants.md](rules_and_invariants.md)); la UX de
caducidad es 401 → `/login?expired=1` (TASK-0049).

### El padre no marca una factura como pagada

«He pagado» (TASK-0068) crea una tarea de staff. El cobro lo confirma el
equipo en la cola. Un padre nunca hace `PATCH` de `FamilyInvoice` (403).
`pending_review` sigue siendo 404 (RULE-017).

### Huecos del mes

`GET /billing/unbilled` (TASK-0065): contratos `active` vigentes este mes
cuya familia no tiene ninguna `FamilyInvoice` con `issue_date` en el mes.
Una factura `pending_review` ya enlazada cuenta como hueco tapado: el
documento está en la cola.

### Confirmar cobro e informe del mes

`POST /family-invoices/{id}/confirm-payment` (TASK-0071) marca `paid` y
cierra la tarea de aviso. Un PATCH/bulk a `paid` hace lo mismo (TASK-0070).
`GET /billing/month-report` (TASK-0072) lista por familia esperado, cobrado,
deuda y si falta factura. El padre no recibe `extracted_data` (TASK-0074).
La descarga de PDF no puede salir de `ATTACHMENTS_DIR`, sea la ruta relativa
o absoluta, y se sirve exclusivamente el fichero que apunta `file_path`: los
dos fallbacks por nombre base -uno sobre `original_filename`, que lo controla
quien manda el correo- devolvian los bytes de otro documento cuando el propio
faltaba (TASK-0091).

### Cobros: pagos parciales y fecha de cobro

`POST /family-invoices/{id}/payments` (staff) registra un cobro con su fecha,
importe, método y referencia; `GET` del mismo recurso los lista (el padre
solo los de sus facturas publicadas, RULE-005/RULE-017). Un pago parcial no
salda la factura: la deuda que se ve en familias, cierre del mes y
recordatorios es ya `amount - pagado`. Se rechaza (422) cobrar más de lo que
queda, una factura en revisión o una sin importe (TASK-0157).

«Cobrado» en `/billing/summary` y `/billing/month-report` se mide por la
fecha del **cobro**, no por la de emisión: una factura de agosto cobrada en
septiembre cuenta en septiembre y ya no cambia el cierre de agosto
(TASK-0102). La migración `bc7e2060710e` da fecha de cobro y un `Payment` a
lo que ya constaba como `paid`.

### Avisos a las familias: bandeja de salida

Publicar una factura **encola** el aviso en `notification_outbox`, en la
misma transaccion que la publicacion: o se publica y queda encolado, o no
ocurre ninguna de las dos cosas. El envio real lo hace
`POST /notifications/flush`, que es el unico sitio que toca el SMTP y el
unico que puede afirmar que algo salio (TASK-0104/0105).

- `dedupe_key` es unico en base de datos: una factura se anuncia una vez y
  una familia recibe como mucho un recordatorio de cada tipo al dia. La
  deduplicacion no depende de un check-then-insert.
- `POST /notifications/overdue-reminders` y `due-soon-reminders` devuelven
  `queued` / `already_queued` / `families_without_recipient`, no `sent`: no
  envian, asi que no pueden decir que enviaron.
- `GET /notifications/outbox` (staff) enseña que se mando a cada familia,
  cuando, y el motivo si fallo. Una fila se reintenta hasta 5 veces.
- Medido con Mailpit apagado: el `PATCH` que publica baja de 4,10 s a
  0,036 s, porque el sondeo TCP del transporte sale del camino de la
  peticion.

### Deuda en el listado y avisos del padre

`GET /families` (TASK-0075) incluye `outstanding_amount`, `overdue_amount` y
`unbilled`. Las facturas llevan `days_in_queue` / `days_overdue` (TASK-0076).
El padre tiene `GET /notifications/mine` (TASK-0077): solo vencidas y 7 días
de su familia, nunca `pending_review`. El cierre se exporta en
`GET /billing/month-report.csv` (TASK-0078).

### Ficha, cola y huecos

`GET /family-invoices?family_id=` (TASK-0080): staff filtra; el padre ignora el
param y sigue viendo solo las suyas publicadas. La ficha lista esas facturas
(TASK-0081). El kanban filtra por nombre, sin asignar y cola vieja
(TASK-0082). `POST /billing/unbilled/tasks` (TASK-0083) crea una tarea
«Facturar el mes YYYY-MM» por hueco, sin duplicar las pendientes.

`GET /family-invoices` esta paginado (TASK-0126): `limit` (por defecto 50,
maximo 200) y `offset`, con el total real en la cabecera `X-Total-Count`, que
va expuesta en CORS. La respuesta sigue siendo una lista, asi que nada se
rompe por esto; lo que cambia es que ya no se descarga la tabla entera. El
tablero pide una pagina POR COLUMNA y ofrece «Cargar mas»; las vistas de una
sola familia piden el maximo. La paginacion se aplica siempre DESPUES del
filtrado por familia, asi que un `offset` grande no puede asomar a las
facturas de otra familia (RULE-005).

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
