# AGENTS.md — Manual de operaciones de CRM Transporte

Normativa para **agentes IA y personas** que trabajen en este repositorio.
Las reglas son numeradas y vinculantes. El resumen humano vive en
[docs/CONTRIBUTING.md](docs/CONTRIBUTING.md); el ledger de tareas, en [ISSUES.md](ISSUES.md).

---

## Inicio rápido

```bash
corepack enable 2>/dev/null || npm i -g pnpm@9.12.0
pnpm install
pnpm build && pnpm lint && pnpm format:check   # lado web
pnpm dev                                        # Web :3000

cd apps/api && uv sync --all-groups && uv run pytest   # lado API (requiere Python 3.12+/uv)
```

---

## Mapa del proyecto

| Ruta      | Contenido                           | Estado       |
| --------- | ----------------------------------- | ------------ |
| apps/api  | FastAPI · health check · sin DB aún | Operativo    |
| apps/web  | Next.js 15 + Tailwind v4 · landing  | Operativo    |
| ISSUES.md | ledger de tareas TASK-XXXX          | Fuente única |

---

## Reglas

### RULE-001 — Ledger de tareas obligatorio

Todo trabajo no trivial requiere un id `TASK-XXXX` en ISSUES.md **antes** de
empezar: se da de alta si no existe, se marca `En curso` al comenzar y solo
pasa a `Hecha` cuando las puertas de calidad (RULE-004) pasan. Trivial =
typos o cambios de una línea.

### RULE-002 — Ramas y commits

Prohibido commitear a `main` (excepto el commit inicial de fundación del
repositorio). Ramas `feature|fix|chore|docs/task-XXXX-slug-corto`.
Conventional Commits en español citando la TASK: `feat(api): ... (TASK-0018)`.
Nunca reescribas historia compartida ni hagas force-push a ramas del equipo.

### RULE-003 — Pull Requests

Todo cambio llega a `main` vía PR: review obligatoria, squash merge, plantilla
completa (qué / cómo probarlo / migraciones si aplica). Vincula `Closes #n`
cuando haya issue de GitHub paralelo al TASK.

### RULE-004 — Puertas de calidad

Antes de pedir review y antes de merge, en verde y en este orden:

```bash
pnpm format:check && pnpm lint && pnpm build && pnpm test && pnpm e2e
```

Si el cambio toca `apps/api`, además:

```bash
cd apps/api && uv run ruff format --check . && uv run ruff check . && uv run pytest
```

Prohibido `--no-verify`, saltarse hooks o desactivar tests para que pase.

### RULE-005 — Invariante de acceso por familia

Toda consulta de datos de negocio hecha por un usuario `role = parent` filtra
por su `familyId`. Ningún endpoint de negocio sin guard que lo aplique. Es el
invariante más importante del producto — una fuga entre familias (que una
familia vea documentos de otra) es el bug más grave posible aquí.

### RULE-006 — Secretos y entorno

`.env` jamás al repo. Toda variable nueva se añade a `.env.example` y a la
tabla de variables de `docs/ARCHITECTURE.md` en el mismo PR. Si un secreto se
filtra (incluyendo credenciales de Gmail API), rota primero, documenta después.

### RULE-007 — Disciplina de migraciones

El schema (SQLAlchemy/Alembic) cambia solo con migración creada en el mismo
PR, aviso al equipo, y nunca editando migraciones ya aplicadas. Bump mayor de
FastAPI/SQLAlchemy/Next = TASK propio.

### RULE-008 — Tests esperados

Lógica nueva → unit test. Fix de bug → test de regresión que falle antes del
fix. Flujo UI crítico → e2e Playwright. La extracción de PDF/XML se prueba con
fixtures de correos reales (anonimizados), no con mocks — un mock no detecta
que cambió el formato de un proveedor real. Sin excepciones "luego lo añado".

### RULE-009 — Documentación en el mismo PR

Si cambias comportamiento, comandos, endpoints o variables: actualizas
ARCHITECTURE/SETUP/DATA_MODEL en el mismo PR. La documentación "para después"
no ocurre.

### RULE-010 — Política de dependencias

Mínimo indispensable; justifica cada dependencia nueva en el PR. Bump de
packageManager o de mayores (Next/FastAPI/Tailwind) es TASK propio con gates
completos.

### RULE-011 — Convenciones de idioma

Documentación, comentarios de commit y copy de UI en español. Identificadores,
comentarios de código y nombres de rama en inglés. Sin mezclas dentro del
mismo artefacto.

### RULE-012 — Estilo: lo deciden las herramientas

Prettier/ESLint (JS) y ruff (Python) deciden el estilo; cero debate de formato
en review. Los hooks arreglan lo formateable automáticamente; lo que el
linter no arregla, no se mergea.

### RULE-013 — Protocolo del ledger

Estados y transiciones válidos: Pendiente → En curso → Hecha, o Bloqueada /
Cancelada (con motivo). Ids inmutables, nunca se reutilizan ni renumeran.
Cerrar = fecha + PR. Cancelar ≠ borrar.

### RULE-014 — Meta-regla sobre reglas

Reglas nuevas: número siguiente correlativo, nunca renumerar ni eliminar en
silencio. Modificar una regla exige PR propio referenciado desde ISSUES.md.

### RULE-015 — Datos de menores por defecto protegidos

`Student` contiene datos de menores. Ninguna feature nueva expone, exporta o
loguea datos de un `Student` sin pasar antes por una revisión explícita de
privacidad en el PR (qué campos, quién los ve, cuánto se retienen). Los logs
de aplicación nunca incluyen `extractedData` completo de una factura ni datos
personales de `Student` en texto plano.

### RULE-016 — Adjuntos no confiables

Todo fichero descargado de Gmail (PDF, ZIP, XML) pasa por escaneo antivirus y
por límites de tamaño/nº de ficheros al descomprimir **antes** de que
cualquier parser lo abra. Ningún parser de PDF/XML corre sin límite de
recursos (protección zip-bomb / decompression bomb). Esto es Fase 2, no se
difiere a "robustez" (RULE-008 aplica: es lógica de seguridad, necesita test).

### RULE-017 — El padre no ve facturas sin revisar

Un `User` con `role = parent` nunca lista ni lee por id una `FamilyInvoice`
en `status = pending_review`. El dato extraído todavía no es un dato de
negocio publicado: puede estar mal clasificado, mal emparejado o contener
identificadores de un menor (RULE-015). Acceso denegado → `404`, igual que
RULE-005. Staff/admin sí las ven: son el contenido de la cola de revisión.

---

## Definición de hecho (Definition of Done)

- [ ] Gates RULE-004 en verde en local y en CI
- [ ] Tests incluidos según RULE-008
- [ ] Docs actualizadas según RULE-009
- [ ] Si toca `Student`/facturas: revisión de privacidad según RULE-015
- [ ] Entradas del ledger actualizadas (RULE-001/RULE-013)
- [ ] PR abierta hacia main, revisada y squash-mergeada
