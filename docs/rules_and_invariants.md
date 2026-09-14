# Reglas e invariantes — inventario vs. código

Mapa RULE-XXX → código, más invariantes de producto. La normativa vinculante
sigue en [AGENTS.md](../AGENTS.md); esto no la sustituye.

Última revisión: 2026-09-14 (campaña TASK-0046).

---

## Inventario RULE-XXX

| Regla                               | ¿Se cumple?                      | Dónde se nota                                                                                                            |
| ----------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| RULE-001 ledger TASK                | Sí en esta campaña               | TASK-0043 … TASK-0049 dadas de alta en ISSUES.md antes de tocar código.                                                  |
| RULE-002 ramas / no commit a `main` | Proceso                          | Rama `feature/task-0046-architecture-and-product`. Sin remoto (TASK-0010).                                               |
| RULE-003 PRs                        | Bloqueada                        | Igual: no hay remoto.                                                                                                    |
| RULE-004 gates                      | Sí, cuando se corren             | `pnpm` + `uv run pytest` / ruff. E2E no se corre a la vez que `pnpm dev` (gotcha `.next`).                               |
| RULE-005 `familyId`                 | Sí                               | `ensure_family_access` (404, `family_id` nulo tampoco es del padre), filtros de listado, `tests/test_family_scoping.py`. |
| RULE-006 secretos                   | Sí                               | `.env` gitignored; `.env.example` documenta variables. `JWT_SECRET` de dev no se usa fuera de local.                     |
| RULE-007 migraciones                | Sí                               | 5 migraciones Alembic; esta campaña no toca schema.                                                                      |
| RULE-008 tests                      | Sí                               | pytest para lógica nueva; e2e Playwright para flujos UI.                                                                 |
| RULE-009 docs en el mismo PR        | Sí                               | Este fichero, `changes_architecture.md`, ARCHITECTURE/DATA_MODEL/ROADMAP/README.                                         |
| RULE-010 dependencias               | Sí                               | Sin shadcn ni icon packs. `@dnd-kit/core` ya justificado (TASK-0042).                                                    |
| RULE-011 idioma                     | Sí                               | UI y docs en español; código en inglés.                                                                                  |
| RULE-012 estilo por herramientas    | Sí                               | Prettier / ESLint / ruff.                                                                                                |
| RULE-013 protocolo del ledger       | Sí                               | Ids correlativos, no se reutilizan.                                                                                      |
| RULE-014 meta-reglas                | Sí                               | RULE-017 es el último correlativo; no se renumeran.                                                                      |
| RULE-015 datos de menores           | Sí, con revisión en esta campaña | Ver tabla de privacidad más abajo. Logs no vuelcan `extracted_data` ni PII de `Student`.                                 |
| RULE-016 adjuntos no confiables     | Sí                               | `safe_zip` + `ClamdScanner`; `/ingestion/run` 503 si clamd no responde. No se degrada.                                   |
| RULE-017 padre vs. `pending_review` | Sí, cerrado del todo             | Listado y GET por id → 404. **Además** el correo de “nueva factura” solo sale cuando el estado deja `pending_review`.    |

---

## Invariantes de producto (además de las RULE)

1. **Una sola empresa, nunca multi-tenant.** No hay `Organization`. Staff/admin
   ven todas las familias; el padre, solo la suya.
2. **Matching automático no sustituye revisión.** Aunque haya un único alumno
   que coincida, `status` sigue `pending_review`.
3. **Anonimizar ≠ borrar facturas.** Se pisan nombre/dirección/email/colegio;
   los importes se conservan por obligación contable.
4. **Notas y tareas son internas.** Routers `notes` y `tasks` exigen
   staff/admin. Un padre no las tiene en el menú ni en la API.
5. **RULE-017.** Un `parent` no lista ni lee `FamilyInvoice` en
   `pending_review` (404). Hasta que staff cambia el estado, el dato extraído
   no es un dato de negocio publicado.
6. **Notificar al publicar, no al ingerir.** `notify_new_family_invoice` se
   dispara en el PATCH de `FamilyInvoice` cuando el estado **sale** de
   `pending_review` y hay `family_id`. La ingesta no avisa. Si no hay familia
   enlazada, no hay correo.
7. **`ensure_family_access` con `family_id` nulo.** Una factura sin enlazar
   nunca es de un padre → 404. Implementado en `dependencies.py`.

---

## Revisión de privacidad (RULE-015) — esta campaña

| Campo                                            | Quién lo ve                            | Notas                                                                                              |
| ------------------------------------------------ | -------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `Student.name`, `school`, `birth_date`, `status` | staff / admin, ficha de familia        | No hay pantalla de alumnos para el padre.                                                          |
| `Student` en `GET /students`                     | padre, **solo su `familyId`**, vía API | Sin UI. No se añade.                                                                               |
| `FamilyInvoice.extracted_data`                   | staff en cola de revisión              | El padre no ve la factura hasta publicarla; el export RGPD del padre **excluye** `pending_review`. |
| Export RGPD JSON                                 | padre (su familia) y staff             | Incluye alumnos a propósito (derecho de acceso). No se loguea.                                     |
| Logs de aplicación                               | —                                      | Prohibido volcar `extracted_data` completo o PII de menor en texto plano.                          |

---

## Huecos que aún no son regla

- **JWT en `localStorage`.** Cualquier XSS lee la sesión. No hay refresh.
  Mitigación de UX (TASK-0049): 401 → login con aviso. No se eleva a RULE
  hasta que haya hosting, CSP y una decisión de cookies httpOnly.
- **Padre y `GET /students`.** Coherente con RULE-005; abrir UI exige pasar
  otra vez por RULE-015.
- **Política RGPD de retención** (cuándo anonimizar de oficio) — TASK-0012,
  decisión de negocio, no de código.
