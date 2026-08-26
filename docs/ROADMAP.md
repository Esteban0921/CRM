# Roadmap de CRM Transporte

> El estado real de cada tarea vive en [ISSUES.md](../ISSUES.md) con ids `TASK-XXXX`.
> Este documento narra objetivos y orden; **no duplica estados**.

CRM interno para una empresa de transporte escolar: gestiona familias,
alumnos y la facturación asociada (a familias y de proveedores), con ingesta
automática de correo como módulo dentro del CRM — no como proyecto aparte.
El detalle original de ese módulo de ingesta vive en [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md).

---

## Fase 0 – Fundación del repositorio ✅ COMPLETADA

**Objetivo:** clonar, instalar y trabajar sin fricción, con calidad automatizada.

| Tareas                                                                          | Ids                   |
| ------------------------------------------------------------------------------- | --------------------- |
| Monorepo (pnpm+turbo para JS, uv/pyproject para Python) + documentación inicial | TASK-0001             |
| API FastAPI mínima (`/health`), CORS, sin DB                                    | TASK-0002             |
| Web Next.js 15 + Tailwind con landing inicial                                   | TASK-0003             |
| ESLint + Prettier + Husky (JS) y ruff (API); tests unit/e2e; CI                 | TASK-0004 … TASK-0006 |
| Docker Compose (Postgres/Redis/Mailpit)                                         | TASK-0007             |
| Python 3.12+/uv instalados y docker compose verificado en máquina real          | TASK-0008, TASK-0009  |

Criterio cumplido: `pnpm install && pnpm build && pnpm lint && pnpm format:check && pnpm e2e`
pasan en local. El lado API está además verificado en runtime contra
Postgres real (TASK-0009): las 5 migraciones Alembic aplicadas y las 13
tablas confirmadas en el motor real, no solo en el SQLite de los tests.

---

## Fase 1 – Identidad, familias y alumnos ✅ COMPLETADA

**Objetivo:** login por rol (`parent`/`staff`/`admin`) y CRUD interno de
familias, alumnos y contratos, con el invariante `familyId` ya aplicado.

- ✅ Backend: modelos `User`/`Family`/`Student`/`Contract` (SQLAlchemy) + primera migración Alembic (TASK-0016).
- ✅ Backend: auth JWT + hash de contraseña, `POST /auth/login` (TASK-0017).
- ✅ Backend: dependencia que inyecta/fuerza `familyId` para rol `parent` + CRUD interno (rol `staff`/`admin`) de familias/alumnos/contratos (TASK-0018).
- ✅ Frontend: login; layout autenticado distinto para padre vs. staff (TASK-0019).
- ✅ Backend: alta de `User` (incluye padres) por staff/admin (TASK-0020).

Migración ya aplicada y verificada contra Postgres real (TASK-0009). Sigue
pendiente conectar el repo a un remoto para ejercitar PRs de verdad (TASK-0010).

No se empieza a construir sobre datos reales de facturación hasta que este
invariante esté probado con tests — es la pieza de seguridad más importante
del proyecto (equivalente a RULE-005).

---

## Fase 2 – Ingesta de correo y extracción ✅ completa (Gmail aún simulado)

**Objetivo:** el pipeline descrito en [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md)
funcionando de punta a punta, escribiendo en `FamilyInvoice` / `SupplierInvoice`.

Decisión del usuario (2026-08-25): simular credenciales de Gmail en vez de
esperar a las reales, para poder construir y probar el pipeline entero ya.
Todo lo de abajo está construido y con 85 tests pasando contra un
`FakeGmailClient`; pasar a Gmail real es sustituir una implementación detrás
del mismo protocolo (`GmailClient`), no rediseñar nada (TASK-0032, pospuesta
a propósito). El resto de piezas simuladas (antivirus, SMTP) ya se
verificaron contra servicios reales — ver más abajo.

- ✅ Modelos `Supplier`/`Email`/`Document`/`FamilyInvoice`/`SupplierInvoice`/`AuditLog` + migración (TASK-0021).
- ✅ Orquestador de ingesta + `GmailClient`/`FakeGmailClient` (TASK-0022): idempotencia por `gmail_id`, etiquetas `AUTO/PROCESSED`/`AUTO/FAILED`.
- ✅ Clasificación por reglas + extracción de campos por plantilla, estilo `invoice2data` (TASK-0023).
- ✅ Límites zip-bomb (ratio/tamaño/nº ficheros) + interfaz de escaneo (`ClamdScanner` real en Docker, ver TASK-0033) (TASK-0013).
- ✅ Distinción factura-a-familia vs. factura-de-proveedor (por email de `Supplier` conocido).
- ✅ Matching automático de `FamilyInvoice` → `Family` por nombre de alumno (TASK-0030) — ambiguo o sin match queda para revisión manual.
- ✅ Cola de revisión: `family-invoices`/`supplier-invoices`, ordenada por `confidence` (TASK-0014).
- ✅ Notificación por email a la familia cuando se enlaza una factura nueva (TASK-0015).
- ✅ `ClamdScanner` real contra un daemon `clamd` en Docker, verificado con archivo limpio y con el string EICAR (TASK-0033).
- ✅ `SmtpEmailSender` real contra Mailpit, verificado end-to-end vía la API REST de Mailpit (TASK-0034).
- ✅ `POST /ingestion/run` (staff/admin): el orquestador no tenía ningún punto de entrada real hasta ahora, solo se ejecutaba en tests (TASK-0041, hallazgo de esta sesión).
- ⏳ Extracción real de texto de PDF — pypdf/pdfplumber (TASK-0031, necesita muestras reales).

---

## Fase 3 – Dashboards ✅ completa (con huecos menores anotados)

**Objetivo:** padres consultando sus facturas; staff revisando y corrigiendo.

- ✅ API: `family-invoices`/`supplier-invoices` (listado filtrable, detalle, corrección con audit trail).
- ✅ API: notas internas (`Note`) y tareas/recordatorios (`Task`) para staff.
- ✅ API: exportación de datos de una familia (`GET /families/{id}/export`, RGPD).
- ✅ Frontend: `/dashboard` (padre) lista sus `FamilyInvoice` reales; `/dashboard/invoices` (staff) es la cola de revisión (TASK-0035).
- ✅ Frontend: `/dashboard/families` (alta/listado) y `/dashboard/families/[id]` (ficha con alumnos, notas, tareas, exportar/anonimizar RGPD) (TASK-0036/0037/0038).
- ✅ Frontend: `/dashboard/invoices` como tablero kanban por estado, inspirado en Huly (TASK-0042) — ver "Inspiración de diseño" más abajo.
- ⏳ Frontend: editar un alumno ya creado, y cualquier pantalla de `Contract` (TASK-0039).
- ⏳ Descarga real (fichero) del export RGPD — hoy vuelca a la consola del navegador (TASK-0040).
- ⏳ Exportación CSV/Excel de la vista filtrada de facturas (uso administrativo masivo, distinto del export RGPD).
- ⏳ Copiar los campos extraídos (`extracted_data`) a las columnas estructuradas `amount`/`issue_date` de la factura (TASK-0043).

### Inspiración de diseño (2026-08-26): Huly, solo en superficie

El usuario pidió tomar [Huly](https://github.com/hcengineering/platform) como
referencia. Es una plataforma multi-tenant de escala mucho mayor (Svelte,
30+ microservicios, CockroachDB, Kafka, Elasticsearch, MinIO, Y.js) — no
aplicable aquí: se confirmó de nuevo que este CRM es de uso interno de una
sola empresa, para siempre. Se toma inspiración de diseño/UX y vistas
concretas sobre el stack actual, no la arquitectura. Primera pieza: el
tablero kanban de la cola de revisión (TASK-0042).

---

## Fase 4 – Robustez y notificaciones ✅ verificada contra servicios reales

- ✅ Notificación por email a la familia cuando se enlaza una factura nueva (TASK-0015), verificada contra `SmtpEmailSender` real + Mailpit (TASK-0034).
- ✅ Retención/RGPD: mecanismo de anonimización (`POST /families/{id}/anonymize`, TASK-0012) — la política (cuándo, con qué base legal) sigue sin decidir.
- ⏳ Recordatorios automáticos de vencimiento próximo (hoy `Task` es manual, staff lo crea a mano).
- ⏳ Reintentos con backoff, dead-letter para correos fallidos (hoy un fallo marca `AUTO/FAILED` y para ahí).

---

## Fase 5+ — Rutas, vehículos y conductores (fuera de alcance por ahora)

Se desglosará en TASKs cuando se decida abordarla, siguiendo el protocolo de
ISSUES.md. `Contract` ya está preparado para añadir `routeId` sin rediseño.

---

## Cómo usar este Roadmap

1. Las tareas se gestionan SOLO desde ISSUES.md (alta, estado, cierre).
2. Ramas `feature/task-XXXX-slug`; PRs revisados; squash merge.
3. Al cerrar tareas de una fase, comprobar qué queda pendiente antes de abrir la siguiente.
