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

| Tareas                                                                                  | Ids                   |
| --------------------------------------------------------------------------------------- | --------------------- |
| Monorepo (pnpm+turbo para JS, uv/pyproject para Python) + documentación inicial         | TASK-0001             |
| API FastAPI mínima (`/health`), CORS, sin DB                                            | TASK-0002             |
| Web Next.js 15 + Tailwind con landing inicial                                           | TASK-0003             |
| ESLint + Prettier + Husky (JS) y ruff (API); tests unit/e2e; CI                         | TASK-0004 … TASK-0006 |
| Docker Compose (Postgres/Redis/Mailpit)                                                 | TASK-0007             |
| Pendiente (humano): instalar Python 3.12+/uv y verificar docker compose en máquina real | TASK-0008, TASK-0009  |

Criterio cumplido: `pnpm install && pnpm build && pnpm lint && pnpm format:check && pnpm e2e`
pasan en local sin Docker ni Python instalados (el lado API queda listo para
instalar pero sin verificar todavía — ver TASK-0008).

---

## Fase 1 – Identidad, familias y alumnos (estimación pendiente)

**Objetivo:** login por rol (`parent`/`staff`/`admin`) y CRUD interno de
familias, alumnos y contratos, con el invariante `familyId` ya aplicado.

- Backend: Prisma-equivalente en Python (SQLAlchemy + Alembic), modelos
  `User`/`Family`/`Student`/`Contract`, primera migración.
- Backend: auth JWT + guard que inyecta `familyId` para rol `parent`.
- Backend: CRUD interno (rol `staff`/`admin`) de familias/alumnos/contratos.
- Frontend: login; layout autenticado distinto para padre vs. staff.

No se empieza a construir sobre datos reales de facturación hasta que este
invariante esté probado con tests — es la pieza de seguridad más importante
del proyecto (equivalente a RULE-005).

---

## Fase 2 – Ingesta de correo y extracción

**Objetivo:** el pipeline descrito en [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md)
funcionando de punta a punta, escribiendo en `FamilyInvoice` / `SupplierInvoice`
en vez de en una tabla `documents` genérica.

- Conexión Gmail API (OAuth, cuenta de pruebas separada de la real).
- Worker de ingesta (Celery o RQ + Redis), descarga de adjuntos, extracción de ZIP.
- Clasificación (reglas deterministas primero) + extracción PDF/XML.
- Escaneo de adjuntos (antivirus) y límites de tamaño/descompresión antes de procesar
  cualquier fichero no confiable — bloqueante, no se difiere.
- Distinción factura-a-familia vs. factura-de-proveedor desde la clasificación.

---

## Fase 3 – Dashboards

**Objetivo:** padres consultando sus facturas; staff revisando y corrigiendo.

- Dashboard padre: listado/detalle de `FamilyInvoice` propias, descarga, estado.
- Panel staff: cola de revisión por confianza baja, corrección manual
  (con `AuditLog`), gestión de `SupplierInvoice`.
- Exportación CSV/Excel de la vista filtrada.

---

## Fase 4 – Robustez y notificaciones

- Notificación (email vía Mailpit en dev) a la familia cuando llega una factura nueva.
- Recordatorios de vencimiento próximo.
- Reintentos con backoff, dead-letter para correos fallidos.
- Retención/RGPD: política de borrado y exportación de datos personales.

---

## Fase 5+ — Rutas, vehículos y conductores (fuera de alcance por ahora)

Se desglosará en TASKs cuando se decida abordarla, siguiendo el protocolo de
ISSUES.md. `Contract` ya está preparado para añadir `routeId` sin rediseño.

---

## Cómo usar este Roadmap

1. Las tareas se gestionan SOLO desde ISSUES.md (alta, estado, cierre).
2. Ramas `feature/task-XXXX-slug`; PRs revisados; squash merge.
3. Al cerrar tareas de una fase, comprobar qué queda pendiente antes de abrir la siguiente.
