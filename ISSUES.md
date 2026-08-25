# ISSUES.md — Ledger de tareas de CRM Transporte

Este fichero es la **fuente única de verdad** del trabajo del proyecto. Cada
tarea tiene un identificador estable `TASK-XXXX`; los estados viven aquí y
solo aquí.

## Protocolo del ledger (normativa completa en AGENTS.md: RULE-001 y RULE-013)

1. Antes de empezar un trabajo no trivial, alta la entrada con el siguiente id secuencial.
2. Estados válidos: `Pendiente → En curso → Hecha`, o `Bloqueada` / `Cancelada`.
3. Un id **nunca** se reutiliza ni se renumera; lo cancelado queda registrado como `Cancelada`.
4. Cada PR referencia sus TASK en título y commits (p. ej. `(TASK-0002)`).
5. Al cerrar: fecha de cierre y referencia al PR que lo resolvió.
6. ROADMAP.md narra las fases y enlaza ids; nunca duplica estados.

---

## Fase 0 — Fundación operativa

| ID        | Título                                                                              | Responsable | Estado    | Cierre     | Refs / Notas                                                                                                           |
| --------- | ----------------------------------------------------------------------------------- | ----------- | --------- | ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| TASK-0001 | Estructura monorepo (pnpm+turbo para JS, uv/pyproject para Python) + docs iniciales | Agente      | Hecha     | 2026-08-25 | Commit inicial; incluye ARCHITECTURE/DATA_MODEL/ROADMAP/AGENTS/CONTRIBUTING/SETUP                                      |
| TASK-0002 | API FastAPI mínima: GET /health, CORS, puerto por API_PORT, sin DB                  | Agente      | Hecha     | 2026-08-25 | SQLAlchemy diferido a Fase 1; sin verificar en runtime (falta Python/uv, TASK-0008)                                    |
| TASK-0003 | Web Next.js 15 + Tailwind v4 con landing "Hello CRM Transporte"                     | Agente      | Hecha     | 2026-08-25 | shadcn/ui diferido a cuando haya UI real de dashboard                                                                  |
| TASK-0004 | ESLint 9 + Prettier (JS) y ruff (API) + Husky/lint-staged unificado                 | Agente      | Hecha     | 2026-08-25 | Un solo hook pre-commit para ambos stacks                                                                              |
| TASK-0005 | Tests: integración API (`/health`) y E2E Playwright de la landing                   | Agente      | Hecha     | 2026-08-25 | API: pytest + TestClient (sin ejecutar, falta Python — TASK-0008). Web: e2e verificado en verde                        |
| TASK-0006 | Workflow CI GitHub Actions: JS (format→lint→build→test→e2e) + API (ruff+pytest)     | Agente      | Hecha     | 2026-08-25 | `.github/workflows/ci.yml`; sin ejecutar todavía (no hay remoto configurado)                                           |
| TASK-0007 | Docker Compose (Postgres 16, Redis 7, Mailpit)                                      | Agente      | Hecha     | 2026-08-25 | Sin verificar en máquina real (Docker no instalado aquí)                                                               |
| TASK-0008 | Instalar Python 3.12+ y uv en la máquina de desarrollo                              | Agente      | Hecha     | 2026-08-25 | Python 3.12.10 + uv 0.12.5 via winget/pip, con permiso explícito del usuario. TASK-0002/0005 ya verificados en runtime |
| TASK-0009 | Verificar docker compose (Postgres/Redis/Mailpit) en máquina real                   | Usuario     | Pendiente | —          | Requiere Docker Desktop instalado                                                                                      |
| TASK-0010 | Conectar el repo a un remoto Git (GitHub u otro) y validar el workflow de PR        | Usuario     | Pendiente | —          | Sin esto, RULE-002/RULE-003 (ramas/PR) no se pueden ejercitar de verdad                                                |

## Auditoría inicial (2026-08-25) — hallazgos que informaron el diseño de Fase 0

Estos puntos surgieron al auditar `docs/SPEC_ORIGINAL.md` antes de escribir
código y ya están reflejados en `docs/ARCHITECTURE.md` / `AGENTS.md`. Se listan
aquí para que no se pierdan de vista al planificar Fase 1/2.

| ID        | Título                                                                       | Responsable    | Estado                              | Cierre     | Refs / Notas                                                                                                                                                                                                                                                                                                              |
| --------- | ---------------------------------------------------------------------------- | -------------- | ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TASK-0011 | Diseñar invariante de acceso por `familyId` antes de construir el dashboard  | Agente         | Hecha                               | 2026-08-25 | Superada por la implementación real en TASK-0018 (`ensure_family_access` + tests)                                                                                                                                                                                                                                         |
| TASK-0012 | Política RGPD de datos de `Student` (retención, derecho de acceso/supresión) | Agente/Esteban | Mecanismo hecho, política pendiente | 2026-08-25 | `GET /families/{id}/export` + `POST /families/{id}/anonymize` construidos y probados (anonimiza identificadores, conserva facturación por obligación contable). **Falta decidir**: cuándo se dispara de oficio (¿tras cuántos años de inactividad?), base legal exacta — eso sigue siendo decisión de Esteban, no técnica |
| TASK-0013 | Escaneo antivirus + límites zip-bomb en la ingesta de adjuntos               | Agente         | Hecha                               | 2026-08-25 | Ver Fase 2                                                                                                                                                                                                                                                                                                                |
| TASK-0014 | Workflow de cola de revisión para documentos con `confidence` baja           | Agente         | Hecha                               | 2026-08-25 | `family-invoices`/`supplier-invoices` (GET lista + detalle + PATCH), ordenados por `confidence` ascendente                                                                                                                                                                                                                |
| TASK-0015 | Definir mecanismo de notificación a familias (nueva factura, recordatorio)   | Agente         | Hecha                               | 2026-08-25 | Ver Fase 2                                                                                                                                                                                                                                                                                                                |

## Fase 1 — Identidad, familias y alumnos

| ID        | Título                                                                         | Responsable | Estado | Cierre     | Refs / Notas                                                                                                                                                                                                          |
| --------- | ------------------------------------------------------------------------------ | ----------- | ------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TASK-0016 | Modelos SQLAlchemy (User/Family/Student/Contract) + migración inicial Alembic  | Agente      | Hecha  | 2026-08-25 | Enums no nativos con `values_callable` (valores en minúscula, no el nombre); migración generada y verificada (upgrade+downgrade) contra SQLite temporal — falta aplicarla contra Postgres real (TASK-0009)            |
| TASK-0017 | Auth: hash de contraseña (bcrypt) + JWT (pyjwt) + `POST /auth/login`           | Agente      | Hecha  | 2026-08-25 | 12 tests (unit + integración con SQLite in-memory vía `TestClient`); sin endpoint de registro público — los `User` los crea `staff`/`admin` (TASK-0018)                                                               |
| TASK-0018 | Dependencia `familyId` (RULE-005) + CRUD interno de familias/alumnos/contratos | Agente      | Hecha  | 2026-08-25 | `ensure_family_access` (404, no 403, para no confirmar existencia de otras familias); 12 tests nuevos, incluyendo que un padre nunca puede leer/listar datos de otra familia aunque fuerce el `family_id` en la query |
| TASK-0019 | Frontend: login + layout autenticado (padre vs. staff)                         | Agente      | Hecha  | 2026-08-25 | `/login` + `/dashboard` con `AuthProvider`; 3 e2e nuevos (login ok, login fallido, redirect sin sesión) mockeando la API con `page.route()` — sin API real corriendo                                                  |
| TASK-0020 | Endpoint `POST /users` (alta de `User` por staff/admin, incl. padres)          | Agente      | Hecha  | 2026-08-25 | Necesario para poder dar de alta el primer padre de una familia; `family_id` obligatorio si `role=parent`; email duplicado → 409                                                                                      |

## Fase 2 — Ingesta de correo y facturación

| ID        | Título                                                                                       | Responsable | Estado | Cierre     | Refs / Notas                                                                                                                                                                                                                  |
| --------- | -------------------------------------------------------------------------------------------- | ----------- | ------ | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TASK-0021 | Modelos Supplier/Email/Document/FamilyInvoice/SupplierInvoice/AuditLog + migración           | Agente      | Hecha  | 2026-08-25 | Solo el esquema; sin pipeline real todavía. 6 tests nuevos (30 en total). Migración verificada (upgrade/downgrade encadenado) contra SQLite — Postgres real sigue pendiente (TASK-0009)                                       |
| TASK-0022 | Cliente Gmail simulado (`GmailClient` protocol + `FakeGmailClient`) + orquestador de ingesta | Agente      | Hecha  | 2026-08-25 | Decisión 2026-08-25 del usuario: simular credenciales en vez de esperar las reales. Swap a un cliente real es cambiar una implementación, no el orquestador                                                                   |
| TASK-0023 | Motor de clasificación (reglas) + extracción de campos por plantilla                         | Agente      | Hecha  | 2026-08-25 | Extracción propia inspirada en el patrón de plantillas de `invoice2data` (ver auditoría comparativa) operando sobre texto ya extraído, no sobre el PDF — evita depender de muestras reales de facturas que todavía no existen |
| TASK-0013 | Límites zip-bomb + interfaz de escaneo de adjuntos (`AttachmentScanner`)                     | Agente      | Hecha  | 2026-08-25 | `NoOpScanner` en dev (no es protección real, lo dice en el nombre y en el log); `ClamdScanner` implementado pero sin verificar — requiere un daemon `clamd` real (TASK-0009/Docker)                                           |
| TASK-0028 | Fix: `family_invoices.family_id` pasa a nullable                                             | Agente      | Hecha  | 2026-08-25 | Descubierto construyendo TASK-0022: la ingesta automática no sabe a qué familia pertenece un documento; queda `pending_review` sin enlazar hasta que staff lo asigna                                                          |
| TASK-0029 | Fix: `suppliers.email` (nuevo campo)                                                         | Agente      | Hecha  | 2026-08-25 | Descubierto construyendo TASK-0023: sin esto, `classify_document` no tenía forma de distinguir proveedor conocido vs. familia                                                                                                 |

4 migraciones en total (TASK-0016, TASK-0021, TASK-0028, TASK-0029), cadena
completa upgrade/downgrade verificada contra SQLite. **50 tests de API**, 4
e2e de web. Bugs reales que salieron solo al ejecutar el pipeline de punta a
punta (no al escribirlo): una función sin definir (`_hash_bytes`), un regex
de extracción roto por `re.IGNORECASE` sobre una clase de caracteres
mayúscula/minúscula, y un doble de prueba (`FakeGmailClient`) que marcaba
"visto" en el momento equivocado (al leer el mensaje, no al etiquetarlo) —
quedan documentados en los commits, no solo corregidos en silencio.

## Auditoría comparativa 2026-08-25 (repos externos + gap analysis)

A petición del usuario: búsqueda en GitHub de proyectos comparables (CRMs de
transporte escolar, CRMs OSS generalistas, herramientas de extracción de
facturas) para identificar qué le falta al proyecto. Hallazgos y tareas que
generaron:

- **`invoice-x/invoice2data`**: no lo añadimos como dependencia (RULE-010 — no
  necesitamos su CLI ni sus múltiples backends de PDF), pero su patrón de
  "plantilla por proveedor con keywords + regex" es el que adoptamos en
  TASK-0023 en vez de un extractor genérico único.
- **No existe una librería Python madura para Facturae** (el estándar XML
  español) — confirma que la sección 12 de SPEC_ORIGINAL.md (decidir schema)
  sigue siendo trabajo real de desarrollo, no una integración trivial.
- **`barseghyanartur/safezip`** y prior art sobre zip bombs: confirmó el
  enfoque de límites (ratio de compresión + tamaño acumulado + nº de
  ficheros) implementado en TASK-0013; no se añadió como dependencia porque
  la lógica necesaria es ~30 líneas con la librería estándar `zipfile`.
- **CRMs OSS comparables (Krayin, NextCRM, Atomic CRM, open-crm)** tienen de
  serie tres cosas que a nosotros nos faltaban — las tres construidas y
  probadas en esta misma sesión:

| ID        | Título                                                                                         | Responsable | Estado | Cierre     | Refs / Notas                                                                                                |
| --------- | ---------------------------------------------------------------------------------------------- | ----------- | ------ | ---------- | ----------------------------------------------------------------------------------------------------------- |
| TASK-0025 | Notas internas de staff sobre `Family`/`Student`                                               | Agente      | Hecha  | 2026-08-25 | `Note`: alta/listado/borrado, nunca visible para `parent`                                                   |
| TASK-0026 | Historial de cambios (audit trail) extendido a `Family`/`Student`/`Contract`, no solo facturas | Agente      | Hecha  | 2026-08-25 | `audit.record_field_changes()` reutilizado en families/students/contracts/family-invoices/supplier-invoices |
| TASK-0027 | Sistema de tareas/recordatorios de staff vinculados a una familia                              | Agente      | Hecha  | 2026-08-25 | `Task`: CRUD completo, status pending/done/cancelled, ordenado por `due_date`                               |

- **KillBill** (motor de facturación recurrente) se consideró y se descarta
  explícitamente: no encaja con la decisión ya tomada de que las facturas
  llegan por Gmail (no las genera el propio CRM), así que un motor de
  suscripciones sería trabajo no pedido — no se registra como tarea.

## Seguir de "simulado" a "real"

Todo lo de abajo es sustituir una implementación por otra detrás del mismo
contrato/protocolo; no requiere rediseño, solo el recurso externo indicado.
TASK-0030 ya no depende de nada externo — se hizo esta sesión; el resto sigue
bloqueado por credenciales/Docker.

| ID        | Título                                                                            | Responsable | Estado    | Cierre     | Refs / Notas                                                                                                                                                                                                 |
| --------- | --------------------------------------------------------------------------------- | ----------- | --------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| TASK-0030 | Matching automático `FamilyInvoice` → `Family` (por nombre de alumno en el texto) | Agente      | Hecha     | 2026-08-25 | Exactamente una coincidencia entre alumnos activos → enlaza; 0 o >1 (ambiguo) → sigue sin enlazar. Status sigue `pending_review` aunque haya match: ahorra trabajo a staff, no sustituye revisión (RULE-015) |
| TASK-0031 | Extracción real de texto de PDF (pypdf/pdfplumber, spec original)                 | —           | Bloqueada | —          | `extraction.py` opera sobre texto ya extraído (simulado); conectar el backend real necesita muestras reales de facturas (sección 12 SPEC_ORIGINAL.md)                                                        |
| TASK-0032 | Cliente Gmail real (OAuth) implementando el protocolo `GmailClient`               | —           | Bloqueada | —          | Requiere credenciales OAuth + cuenta de pruebas (decisión pendiente del usuario, pospuesta a propósito el 2026-08-25)                                                                                        |
| TASK-0033 | `ClamdScanner` real: daemon `clamd` + `pip install clamd`                         | —           | Pendiente | —          | Requiere Docker (TASK-0009); el código ya existe, sin verificar                                                                                                                                              |
| TASK-0034 | `SmtpEmailSender` real contra Mailpit                                             | —           | Pendiente | —          | Requiere Docker (TASK-0009); probado con `smtplib.SMTP` mockeado, no contra un servidor real                                                                                                                 |

## Resumen de esta sesión extendida (2026-08-25)

Modelos `Note`/`Task` + migración (`506954d2c10f`), 6 migraciones en total
desde TASK-0016, cadena completa upgrade/downgrade verificada contra SQLite.
**85 tests de API** + 4 e2e de web, todos en verde. Con esto, Fase 2 del
[ROADMAP.md](docs/ROADMAP.md) queda completa en su versión simulada, y los
tres hallazgos de la auditoría comparativa (notas, audit trail extendido,
tareas) están construidos, no solo anotados.

## Fase 3 y siguientes — Pendiente de desglosar

Se dan de alta en este ledger conforme se planifiquen, con ids a partir de
TASK-0035, siguiendo el protocolo de arriba. El detalle narrativo de cada
fase vive en [docs/ROADMAP.md](docs/ROADMAP.md).
