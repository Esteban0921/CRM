import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { NextConfig } from 'next';

const dirname = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? '.next',
  // Ancla la raíz del workspace a este repo: evita que Next.js se confunda
  // con el package-lock.json suelto en el home directory del usuario.
  outputFileTracingRoot: path.join(dirname, '../..'),
};

export default nextConfig;
