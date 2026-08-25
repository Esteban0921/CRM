# Cómo contribuimos

Resumen humano del workflow. La normativa completa y vinculante está en
[AGENTS.md](../AGENTS.md) (reglas `RULE-XXX`); el trabajo vivo, en
[ISSUES.md](../ISSUES.md) (`TASK-XXXX`).

1. Elige o da de alta una tarea en ISSUES.md y márcala `En curso`.
2. Rama `feature|fix|chore|docs/task-XXXX-slug-corto` desde `main` actualizado.
3. Trabaja con sus tests. Antes de pedir review, todas las puertas de calidad
   en verde (ver [SETUP.md](SETUP.md)).
4. Pull Request → review → squash merge.
5. Marca la TASK como `Hecha` con fecha y referencia al PR.

Nada se commitea directo a `main`. Nunca se hace force-push a ramas del equipo.

## Idioma

Documentación, commits y copy de UI en español. Identificadores, comentarios
de código y nombres de rama en inglés (RULE-011).

## Dudas de alcance

Este CRM es de uso interno (una empresa, sin multi-tenant). El módulo de
ingesta de correo original está descrito en [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md);
si algo de ese documento choca con [ARCHITECTURE.md](ARCHITECTURE.md) o
[DATA_MODEL.md](DATA_MODEL.md), estos dos mandan — el spec original es
contexto histórico, no la fuente de verdad.
