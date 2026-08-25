import { execSync } from 'node:child_process';

function hasUv() {
  try {
    execSync('uv --version', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

const config = {
  '*.{ts,tsx}': ['prettier --write', 'eslint --fix'],
  '*.{js,cjs,mjs,json,md,yml,yaml}': ['prettier --write'],
};

// uv (TASK-0008) todavia no esta instalado en todas las maquinas del equipo;
// el hook no debe bloquear el commit por eso, solo omitir el lint de apps/api.
if (hasUv()) {
  config['apps/api/**/*.py'] = [
    'uv run --project apps/api ruff format',
    'uv run --project apps/api ruff check --fix',
  ];
}

export default config;
