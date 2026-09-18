import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';

/**
 * Superficie con nivel de elevacion explicito (TASK-0144).
 *
 * Antes toda la aplicacion compartia un unico `shadow-sm`: el DOM computado
 * devolvia exactamente un valor de `box-shadow` en el home, en el kanban y en
 * el listado de familias. Sin capas no hay separacion figura-fondo, y eso es
 * lo que el ojo lee como «plano».
 *
 * - 0: al ras del lienzo (agrupaciones, cabeceras de seccion).
 * - 1: tarjeta de contenido. Lleva brillo superior para despegarse del crema.
 * - 2: elemento flotante (popover, fila arrastrada, barra fija).
 * - 3: panel modal.
 */
const levels = {
  0: 'bg-canvas border border-line',
  1: 'bg-surface border border-line shadow-[var(--shadow-1)] surface-sheen',
  2: 'bg-raised border border-line shadow-[var(--shadow-2)]',
  3: 'bg-overlay border border-line shadow-[var(--shadow-3)]',
} as const;

const paddings = {
  none: '',
  dense: 'p-3',
  md: 'p-5',
  lg: 'p-6',
} as const;

export type SurfaceLevel = keyof typeof levels;

export function Surface({
  level = 1,
  padding = 'md',
  interactive = false,
  className,
  children,
}: {
  level?: SurfaceLevel;
  padding?: keyof typeof paddings;
  interactive?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cx(
        'rounded-xl',
        levels[level],
        paddings[padding],
        interactive &&
          'transition duration-150 hover:-translate-y-px hover:border-line-strong hover:shadow-[var(--shadow-2)]',
        className,
      )}
    >
      {children}
    </div>
  );
}
