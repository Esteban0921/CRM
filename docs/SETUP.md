# Setup local — CRM Transporte

## Requisitos

- Node 22 (ver `.nvmrc`) y pnpm 9 (`corepack enable` o `npm i -g pnpm@9.12.0`)
- Python 3.12+ y [uv](https://docs.astral.sh/uv/) para `apps/api` (**pendiente de instalar en esta máquina — TASK-0008**)
- Docker (opcional en Fase 0; necesario desde Fase 1 para Postgres/Redis — **TASK-0009**)

## Lado web (Next.js) — funciona ya

```bash
pnpm install
pnpm build && pnpm lint && pnpm format:check
pnpm dev      # http://localhost:3000
pnpm e2e      # Playwright contra build de producción (puerto 4123)
```

## Lado API (FastAPI) — requiere Python/uv instalados

```bash
cd apps/api
uv sync --all-groups
uv run uvicorn main:app --reload --app-dir src --port 8000
uv run pytest
uv run ruff format --check . && uv run ruff check .
```

## Infraestructura (Postgres/Redis/Mailpit) — Fase 1+

```bash
docker compose up -d
```

- Postgres: `localhost:5432` (usuario/clave/DB en `docker-compose.yml`)
- Redis: `localhost:6379`
- Mailpit UI: `http://localhost:8025`

## Variables de entorno

Copiar `.env.example` a `.env` y ajustar. Ver tabla completa en
[ARCHITECTURE.md](ARCHITECTURE.md#variables-de-entorno).

## Puertas de calidad antes de un PR

Ver RULE-004 en [AGENTS.md](../AGENTS.md). Resumen:

```bash
pnpm format:check && pnpm lint && pnpm build && pnpm test && pnpm e2e
# y si tocaste apps/api:
cd apps/api && uv run ruff format --check . && uv run ruff check . && uv run pytest
```
