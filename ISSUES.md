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

| ID        | Título                                                                               | Responsable | Estado    | Cierre | Refs / Notas                                                              |
| --------- | ------------------------------------------------------------------------------------ | ----------- | --------- | ------ | ------------------------------------------------------------------------- |
| TASK-0011 | Diseñar invariante de acceso por `familyId` antes de construir el dashboard          | Esteban     | Pendiente | —      | RULE-005; Fase 1, no diferible                                            |
| TASK-0012 | Decidir política RGPD de datos de `Student` (retención, derecho de acceso/supresión) | Esteban     | Pendiente | —      | RULE-015; antes de Fase 3 (dashboard con datos reales)                    |
| TASK-0013 | Escaneo antivirus + límites zip-bomb en la ingesta de adjuntos                       | Esteban     | Pendiente | —      | RULE-016; Fase 2, bloqueante antes de procesar adjuntos reales            |
| TASK-0014 | Workflow de cola de revisión para documentos con `confidence` baja                   | Esteban     | Pendiente | —      | Fase 3; hoy el campo existe en el modelo pero no hay vista/flujo asociado |
| TASK-0015 | Definir mecanismo de notificación a familias (nueva factura, recordatorio)           | Esteban     | Pendiente | —      | Fase 4; el spec original era dashboard "pull-only"                        |

## Fase 1 — Identidad, familias y alumnos

| ID        | Título                                                                         | Responsable | Estado | Cierre     | Refs / Notas                                                                                                                                                                                                          |
| --------- | ------------------------------------------------------------------------------ | ----------- | ------ | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| TASK-0016 | Modelos SQLAlchemy (User/Family/Student/Contract) + migración inicial Alembic  | Agente      | Hecha  | 2026-08-25 | Enums no nativos con `values_callable` (valores en minúscula, no el nombre); migración generada y verificada (upgrade+downgrade) contra SQLite temporal — falta aplicarla contra Postgres real (TASK-0009)            |
| TASK-0017 | Auth: hash de contraseña (bcrypt) + JWT (pyjwt) + `POST /auth/login`           | Agente      | Hecha  | 2026-08-25 | 12 tests (unit + integración con SQLite in-memory vía `TestClient`); sin endpoint de registro público — los `User` los crea `staff`/`admin` (TASK-0018)                                                               |
| TASK-0018 | Dependencia `familyId` (RULE-005) + CRUD interno de familias/alumnos/contratos | Agente      | Hecha  | 2026-08-25 | `ensure_family_access` (404, no 403, para no confirmar existencia de otras familias); 12 tests nuevos, incluyendo que un padre nunca puede leer/listar datos de otra familia aunque fuerce el `family_id` en la query |
| TASK-0019 | Frontend: login + layout autenticado (padre vs. staff)                         | Agente      | Hecha  | 2026-08-25 | `/login` + `/dashboard` con `AuthProvider`; 3 e2e nuevos (login ok, login fallido, redirect sin sesión) mockeando la API con `page.route()` — sin API real corriendo                                                  |
| TASK-0020 | Endpoint `POST /users` (alta de `User` por staff/admin, incl. padres)          | Agente      | Hecha  | 2026-08-25 | Necesario para poder dar de alta el primer padre de una familia; `family_id` obligatorio si `role=parent`; email duplicado → 409                                                                                      |

## Fase 2 y siguientes — Pendiente de desglosar

Las tareas de Fase 2 (ingesta de correo) en adelante se dan de alta en este
ledger conforme se planifiquen, con ids a partir de TASK-0021, siguiendo el
protocolo de arriba. El detalle narrativo de cada fase vive en
[docs/ROADMAP.md](docs/ROADMAP.md).

Requieren una decisión o recurso externo que solo puede aportar el usuario
antes de poder empezar (credenciales Gmail API, cuenta de pruebas, volumen
de correo esperado, schema del XML más frecuente — sección 12 de
[SPEC_ORIGINAL.md](docs/SPEC_ORIGINAL.md)).
