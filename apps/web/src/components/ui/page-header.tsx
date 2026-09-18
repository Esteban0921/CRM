import type { ReactNode } from 'react';

/**
 * Jerarquia real (TASK-0142): el titulo de pagina sube a `text-2xl` con
 * tracking cerrado y peso 700. Antes la cifra de un KPI (30 px) era mas grande
 * que el titulo de la pantalla en la que vivia: jerarquia invertida.
 */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
      <div>
        <h1 className="text-2xl font-bold text-ink">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}

/**
 * Encabezado de seccion dentro de una pagina. La ficha de familia tenia ocho
 * secciones con el mismo `<h2 className="font-medium">` de 16 px en una pagina
 * de 4.859 px de alto: ni un nivel de lectura.
 */
export function SectionHeader({
  title,
  description,
  actions,
  count,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  count?: number;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-xl font-semibold text-ink">{title}</h2>
        {count !== undefined ? (
          <span className="tabular text-sm font-medium text-faint">{count}</span>
        ) : null}
        {description ? <p className="text-sm text-muted">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
