import type { ReactNode } from 'react';

/**
 * Vacio intencionado, no layout roto (TASK-0151).
 *
 * El borde discontinuo a 1.136 px de ancho con el texto alineado a la
 * izquierda no leia como «aqui no hay nada todavia», leia como «esto no ha
 * cargado». Ahora va centrado, acotado y con un glifo.
 *
 * Los `title` son literales asertados en los specs e2e («No hay facturas de
 * proveedor todavia.», «No hay notas de credito.»): se pintan tal cual.
 */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface px-6 py-12 text-center">
      <span
        aria-hidden
        className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-tint text-brand"
      >
        <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" stroke="currentColor">
          <path
            d="M3.5 6.5h13v9a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-9Zm0 0 1.2-2.4a1 1 0 0 1 .9-.6h8.8a1 1 0 0 1 .9.6l1.2 2.4M8 10h4"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <p className="text-lg font-semibold text-ink">{title}</p>
      <p className="max-w-sm text-sm text-muted">{description}</p>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
