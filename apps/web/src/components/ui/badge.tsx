import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';

/**
 * Estado y metadato son dos cosas distintas y se veian igual (TASK-0146).
 *
 * Las cinco tonalidades usaban la misma receta `bg-*-100 text-*-900`: misma
 * forma, mismo peso, misma luminancia. A un metro de distancia
 * `pending_review`, `sent`, `paid` y `overdue` eran la misma pastilla palida,
 * y el chip de confianza pesaba tanto como el estado.
 *
 * Ahora el estado lleva punto de color, borde y peso 600; el metadato
 * (confianza, antiguedad) va en `<Chip>`, de contorno y sin relleno, para que
 * deje de competir. Los nombres de tono se conservan porque `format.ts` los
 * mapea y los tests e2e buscan los textos.
 */
const tones = {
  amber: {
    solid: 'bg-warn-bg text-warn-fg border-warn-line',
    dot: 'bg-warn-fg',
  },
  blue: {
    solid: 'bg-info-bg text-info-fg border-info-line',
    dot: 'bg-info-fg',
  },
  emerald: {
    solid: 'bg-ok-bg text-ok-fg border-ok-line',
    dot: 'bg-ok-fg',
  },
  rose: {
    solid: 'bg-danger-bg text-danger-fg border-danger-line',
    dot: 'bg-danger-fg',
  },
  slate: {
    solid: 'bg-neutral-bg text-neutral-fg border-neutral-line',
    dot: 'bg-neutral-fg',
  },
} as const;

export type BadgeTone = keyof typeof tones;

export function Badge({
  tone = 'slate',
  dot = true,
  children,
}: {
  tone?: BadgeTone;
  /** El punto se quita cuando el badge no representa un estado. */
  dot?: boolean;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5',
        'text-xs font-semibold whitespace-nowrap',
        tones[tone].solid,
      )}
    >
      {dot ? (
        <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', tones[tone].dot)} aria-hidden />
      ) : null}
      {children}
    </span>
  );
}

/**
 * Metadato: confianza de la extraccion, dias en cola, categoria. Contorno, sin
 * relleno y sin punto, para que nunca compita con el estado.
 */
export function Chip({ tone = 'slate', children }: { tone?: BadgeTone; children: ReactNode }) {
  const border = {
    amber: 'border-warn-line text-warn-fg',
    blue: 'border-info-line text-info-fg',
    emerald: 'border-ok-line text-ok-fg',
    rose: 'border-danger-line text-danger-fg',
    slate: 'border-line-strong text-muted',
  } as const;

  return (
    <span
      className={cx(
        'inline-flex items-center rounded-md border bg-transparent px-1.5 py-0.5',
        'text-2xs font-medium whitespace-nowrap',
        border[tone],
      )}
    >
      {children}
    </span>
  );
}
