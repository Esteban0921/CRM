# Cambios de arquitectura — campaña 2026-09-14

Contraste entre lo que documentan [ARCHITECTURE.md](ARCHITECTURE.md),
[ROADMAP.md](ROADMAP.md) e [ISSUES.md](../ISSUES.md) y lo que el producto
hace de verdad. Este fichero **no** sustituye ARCHITECTURE.md: ese es el mapa
del sistema; aquí vive qué se decidió cambiar y qué se deja fuera.

No se reescribe el stack. El CRM sigue siendo interno, una sola empresa,
Next.js 15 + FastAPI + Postgres. Huly se toma solo en superficie (sidebar,
kanban denso, herramienta interna). Gmail real y extracción real de PDF
siguen bloqueados (TASK-0032/0031).

---

## Qué no cambia

- Una sola empresa, nunca `Organization` / multi-tenant.
- `FamilyInvoice` y `SupplierInvoice` son tablas distintas.
- `GmailClient` es un protocolo; hoy `FakeGmailClient`.
- Matching automático **no** salta `pending_review`.
- Adjuntos: ClamAV fail-closed (RULE-016). Un 503 no se degrada a “sin escanear”.
- Auth JWT propio, roles `parent` / `staff` / `admin`.
- Documentación, copy y commits en español; código en inglés (RULE-011).

---

## Contraste diseño vs. runtime (tras esta campaña)

| Afirmación del diseño                       | Estado                                                                                                                                                           |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| JWT access **+ refresh**                    | Solo access token, 15 min, `localStorage`. Al caducar, login con aviso (`?expired=1`). Refresh y cookies httpOnly se posponen a hosting real.                    |
| Spec original: dashboard usable + shadcn/ui | Sistema de diseño **propio** (tokens Tailwind v4 + componentes en `apps/web/src/components`). No se añade shadcn (RULE-010; Huly como referencia de superficie). |
| Cola de revisión usable                     | Kanban con estado **y** asignación de familia (TASK-0044).                                                                                                       |
| Tablero de proveedor                        | `/dashboard/suppliers` (TASK-0045).                                                                                                                              |
| Export RGPD                                 | Descarga `familia-{id}.json` (TASK-0040), no consola.                                                                                                            |
| Ingesta                                     | `POST /ingestion/run` + botón staff “Procesar correos de prueba” (`use_demo_inbox`, TASK-0048).                                                                  |
| Extracción → columnas                       | `amount` / `issue_date` se rellenan al ingerir (TASK-0043, parseo ES).                                                                                           |
| Contratos y edición de alumno               | En la ficha de familia (TASK-0039).                                                                                                                              |
| Aviso a la familia                          | Al **publicar** (sale de `pending_review`), no al ingerir (cierra RULE-017).                                                                                     |
| Home de staff                               | Métricas (pendientes, vencidas, familias) y atajos.                                                                                                              |
| Landing                                     | Marca + frase de valor + acceso, no una línea suelta.                                                                                                            |

---

## Decisiones de esta campaña

1. **Componentes propios, no shadcn/ui.** El spec original lo pedía; TASK-0003 lo aplazó. Añadirlo ahora es una dependencia de UI genérica. Se construye un set mínimo (`button`, `input`, `select`, `badge`, `card`, `dialog`, `toast`, `empty-state`, `metric-card`, shell) con tokens teal/pizarra.
2. **Notificar al publicar.** Un padre no recibe correo de una factura que RULE-017 le oculta.
3. **El padre no ve alumnos en la UI.** `GET /students` sigue filtrado por `familyId` (RULE-005). Mostrarlo en el dashboard del padre exigiría revisión RULE-015; no se hace aquí. Staff sí ve nombre, colegio y fecha de nacimiento en la ficha.
4. **No se alarga el JWT en silencio.** 15 minutos se quedan. La UX deja de ser un redirect mudo.
5. **Ingesta de demo con fixture**, no un textarea de JSON. El payload libre sigue existiendo para tests/API.
6. **Celery/Redis no entra.** El orquestador síncrono no bloquea la demo.

---

## Qué se construye ahora (mapeo a TASK)

| TASK      | Qué                                                                                                     |
| --------- | ------------------------------------------------------------------------------------------------------- |
| TASK-0044 | Ya tomado: asignar familia + RULE-017 en listado/detalle.                                               |
| TASK-0046 | Este documento + [rules_and_invariants.md](rules_and_invariants.md) como fuente viva, y docs alineados. |
| TASK-0047 | Sistema de diseño y rediseño de superficies existentes.                                                 |
| TASK-0043 | Copiar `extracted_data` a `amount` / `issue_date`.                                                      |
| TASK-0048 | Botón de ingesta demo + notificar al publicar.                                                          |
| TASK-0039 | Editar alumno + CRUD de contratos en la ficha.                                                          |
| TASK-0040 | Descarga del export RGPD.                                                                               |
| TASK-0045 | Tablero de facturas de proveedor.                                                                       |
| TASK-0049 | 401 → `/login?expired=1`.                                                                               |

## Qué se deja fuera

- TASK-0031 extracción real de PDF, TASK-0032 Gmail OAuth.
- Refresh token, cookies httpOnly, CSP (cuando haya hosting).
- Cola Celery/RQ, rutas/vehículos/conductores.
- Arquitectura distribuida de Huly.
- Pantalla de alumnos para el padre.

---

## Cómo verificar

Credenciales del seed (`apps/api/seed_dev.py`):

- staff: `staff@crmtransporte-demo.com` / `staff1234`
- padre: `padre@crmtransporte-demo.com` / `padre1234`

1. Login staff → home con métricas, no un enlace suelto.
2. Cola de revisión → asignar familia y mover a “Enviada”.
3. El padre ve esa factura; no ve `pending_review`.
4. “Procesar correos de prueba” crea una factura con importe (no “Importe pendiente”).
5. Ficha de familia: editar alumno, alta de contrato, descargar JSON RGPD.
6. Tablero de proveedor existe en el menú y carga.
7. Tras 15 min (o un 401 forzado), login con “Sesión caducada”.
