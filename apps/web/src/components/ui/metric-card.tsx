import Link from 'next/link';
import { cx } from '@/lib/cx';

/**
 * Tarjeta de metrica con jerarquia (TASK-0147).
 *
 * Las ocho tarjetas del home eran identicas: «Deuda vencida 297,00 EUR»
 * compartia tamano, peso, color, borde y sombra con «Correos fallidos 0». La
 * unica cifra accionable del negocio no tenia ninguna presencia.
 *
 * `emphasis` decide cuanto pesa, y `tone` tine la cifra cuando significa algo
 * (deuda en rojo, cobrado en verde). Un cero se apaga: no puede pesar lo mismo
 * que 999,99 EUR.
 */
const emphasis = {
  hero: 'text-hero',
  default: 'text-3xl',
  compact: 'text-xl',
} as const;

const tones = {
  neutral: 'text-ink',
  debt: 'text-money-debt',
  ok: 'text-money-ok',
  warn: 'text-warn-fg',
} as const;

const accents = {
  neutral: '',
  debt: 'before:bg-danger-line',
  ok: 'before:bg-ok-line',
  warn: 'before:bg-warn-line',
} as const;

function isZeroish(value: string): boolean {
  const digits = value.replace(/[^\d]/g, '');
  return digits.length > 0 && Number(digits) === 0;
}

export function MetricCard({
  label,
  value,
  href,
  hint,
  emphasis: level = 'default',
  tone = 'neutral',
}: {
  label: string;
  value: string;
  href?: string;
  hint?: string;
  emphasis?: keyof typeof emphasis;
  tone?: keyof typeof tones;
}) {
  const muted = isZeroish(value);
  const inner = (
    <>
      <p className="text-xs font-medium tracking-wide text-muted uppercase">{label}</p>
      <p
        className={cx(
          'mt-2 font-bold tabular tracking-tight',
          emphasis[level],
          muted ? 'text-money-zero' : tones[tone],
        )}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </>
  );

  const className = cx(
    'relative block overflow-hidden rounded-xl border border-line bg-surface p-5',
    'shadow-[var(--shadow-1)] surface-sheen',
    // Franja de color arriba: extiende el `border-t-4` del kanban, que es el
    // mejor uso de color que ya tenia la app.
    tone !== 'neutral' &&
      'before:absolute before:inset-x-0 before:top-0 before:h-1 before:content-[""]',
    accents[tone],
    href &&
      'transition duration-150 hover:-translate-y-px hover:border-line-strong hover:shadow-[var(--shadow-2)] active:translate-y-0 active:shadow-[var(--shadow-1)]',
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {inner}
      </Link>
    );
  }
  return <div className={className}>{inner}</div>;
}
