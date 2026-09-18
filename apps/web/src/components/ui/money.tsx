import { cx } from '@/lib/cx';
import { formatAmount } from '@/lib/format';

/**
 * Unico responsable de pintar dinero (TASK-0145).
 *
 * En una cola de cobro el importe era el tercer elemento en jerarquia: 12 px
 * en gris `muted`, por debajo del nombre de la familia y del chip de
 * confianza. Y `tabular-nums` estaba aplicado pero se anulaba por alineacion a
 * la izquierda, asi que una columna con 1,23 / 33,00 / 1234,56 salia dentada.
 *
 * `formatAmount` no se toca: hay tests e2e que buscan la cadena que produce
 * (`/45,00/`). Lo que cambia es como se pinta, no que se pinta.
 */
const emphasis = {
  hero: 'text-3xl font-bold tracking-tight',
  strong: 'text-lg font-semibold',
  normal: 'text-base font-medium',
  quiet: 'text-sm',
} as const;

const tones = {
  auto: '',
  debt: 'text-money-debt',
  ok: 'text-money-ok',
  plain: 'text-money',
} as const;

function isZero(amount: string | null | undefined): boolean {
  if (amount === null || amount === undefined) return false;
  const numeric = Number(amount);
  return Number.isFinite(numeric) && numeric === 0;
}

export function Money({
  amount,
  currency = 'EUR',
  size = 'normal',
  tone = 'auto',
  align = 'right',
  className,
}: {
  amount: string | null | undefined;
  currency?: string;
  size?: keyof typeof emphasis;
  tone?: keyof typeof tones;
  /** Los importes se alinean a la derecha salvo que vayan sueltos en un texto. */
  align?: 'right' | 'left';
  className?: string;
}) {
  const zero = isZero(amount);
  const resolvedTone = tone === 'auto' ? (zero ? 'text-money-zero' : 'text-money') : tones[tone];
  const missing = amount === null || amount === undefined;

  return (
    <span
      className={cx(
        'tabular',
        emphasis[size],
        // Un importe que falta no es un importe: se pinta como lo que es, un
        // hueco, no como una cifra mas.
        missing ? 'text-faint italic' : resolvedTone,
        align === 'right' ? 'text-right tabular-nums' : '',
        className,
      )}
    >
      {formatAmount(amount, currency)}
    </span>
  );
}

/** Celda de tabla con dinero: alineada a la derecha y con cifras tabulares. */
export function MoneyCell({
  amount,
  currency = 'EUR',
  tone = 'auto',
  className,
}: {
  amount: string | null | undefined;
  currency?: string;
  tone?: keyof typeof tones;
  className?: string;
}) {
  return (
    <td className={cx('px-4 py-2.5 text-right', className)}>
      <Money amount={amount} currency={currency} tone={tone} />
    </td>
  );
}
