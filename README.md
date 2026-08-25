# CRM Transporte

**CRM interno**, self-hosted, para una empresa de transporte escolar.

---

## ¿Qué es?

Gestiona la relación con las familias cliente:

- Familias, alumnos y contratos de servicio
- Facturación a familias (el servicio de transporte) y de proveedores (combustible, mantenimiento, seguros)
- Ingesta automática de facturas desde Gmail, clasificación y extracción de metadatos
- Dashboard para que las familias consulten sus facturas; panel interno para el equipo

No es multi-tenant: es el CRM propio de una única empresa.

El detalle original del módulo de ingesta de correo vive en
[docs/SPEC_ORIGINAL.md](docs/SPEC_ORIGINAL.md).

---

## Stack tecnológico

| Capa             | Tecnología                                          |
| ---------------- | --------------------------------------------------- |
| Backend          | Python 3.12+ · FastAPI                              |
| Frontend         | Next.js 15 (App Router) · Tailwind v4               |
| Base de datos    | PostgreSQL 16 (SQLAlchemy + Alembic, Fase 1)        |
| Cola de trabajos | Redis + Celery/RQ (Fase 2)                          |
| Email (dev)      | Mailpit                                             |
| Tests            | pytest · Playwright                                 |
| Calidad          | ruff (API) · ESLint 9 + Prettier (web) · Husky · CI |
| Infra local      | Docker Compose                                      |

---

## Arranque exprés

```bash
pnpm install
pnpm build && pnpm lint      # lado web, sin Docker ni Python
pnpm dev                     # Web :3000
pnpm e2e                     # Playwright contra build de producción
```

El lado API (`apps/api`) requiere Python 3.12+ y [uv](https://docs.astral.sh/uv/)
instalados — ver [docs/SETUP.md](docs/SETUP.md) (pendiente en esta máquina, TASK-0008).

---

## Documentación

| Documento                                 | Descripción                                                          |
| ----------------------------------------- | -------------------------------------------------------------------- |
| [SETUP.md](docs/SETUP.md)                 | Cómo levantar el proyecto en local                                   |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md)   | Arquitectura del sistema, pruebas y tooling                          |
| [DATA_MODEL.md](docs/DATA_MODEL.md)       | Modelo de datos                                                      |
| [ROADMAP.md](docs/ROADMAP.md)             | Plan de trabajo por fases                                            |
| [ISSUES.md](ISSUES.md)                    | **Ledger de tareas TASK-XXXX — fuente única de verdad del trabajo**  |
| [AGENTS.md](AGENTS.md)                    | **Manual de operaciones con reglas RULE-XXX para agentes y humanos** |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md)   | Resumen humano de cómo trabajamos                                    |
| [SPEC_ORIGINAL.md](docs/SPEC_ORIGINAL.md) | Spec original del módulo de ingesta de correo (contexto histórico)   |

---

## Estado actual

**Fase 0 completada — Fundación operativa**: monorepo, API, web, tests
(integración API + E2E web), linting y CI configurados. Pendiente verificar
en runtime lo que requiere Python/uv y Docker instalados (ver ISSUES.md
TASK-0008/0009). Siguiente parada: Fase 1 (identidad, familias y alumnos)
según [docs/ROADMAP.md](docs/ROADMAP.md).

---

## Licencia

Privado / uso interno.
