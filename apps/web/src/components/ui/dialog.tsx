'use client';

import { useCallback, useEffect, useId, useRef, type ReactNode } from 'react';
import { cx } from '@/lib/cx';
import { Button } from './button';

const widths = {
  sm: 'max-w-md',
  md: 'max-w-xl',
  lg: 'max-w-3xl',
  xl: 'max-w-5xl',
} as const;

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Dialogo accesible (TASK-0131).
 *
 * Lo que fallaba, medido: Escape no cerraba; al abrirse el foco se quedaba en
 * `<body>` y tabulando se recorria la pagina de detras antes de entrar en el
 * modal; el fondo seguia haciendo scroll; el `aria-labelledby` usaba un id
 * fijo, asi que dos dialogos en la misma pagina se pisaban; y el ancho era
 * siempre `max-w-md`, lo que dejaba el visor de PDF en un iframe de 406x630 px
 * dentro de un viewport de 1440x900.
 */
export function Dialog({
  open,
  title,
  onClose,
  size = 'sm',
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  size?: keyof typeof widths;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  const focusables = useCallback((): HTMLElement[] => {
    const panel = panelRef.current;
    if (!panel) return [];
    return Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (element) => element.offsetParent !== null || element === document.activeElement,
    );
  }, []);

  useEffect(() => {
    if (!open) return;

    returnFocusRef.current = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';

    const first = focusables()[0] ?? panelRef.current;
    first?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;

      const elements = focusables();
      if (elements.length === 0) return;
      const firstElement = elements[0];
      const lastElement = elements[elements.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === firstElement || !panelRef.current?.contains(active))) {
        event.preventDefault();
        lastElement.focus();
      } else if (!event.shiftKey && active === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }

    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = overflow;
      returnFocusRef.current?.focus?.();
    };
  }, [open, onClose, focusables]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="animate-overlay-in absolute inset-0 bg-ink/50 backdrop-blur-sm"
        aria-label="Cerrar"
        tabIndex={-1}
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={cx(
          'animate-panel-in relative z-10 flex max-h-[90vh] w-full flex-col',
          'rounded-xl border border-line bg-overlay p-5 shadow-[var(--shadow-4)]',
          widths[size],
        )}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-xl font-semibold text-ink">
            {title}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cerrar
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
