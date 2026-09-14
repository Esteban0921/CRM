import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';

const tones = {
  amber: 'bg-amber-100 text-amber-900',
  blue: 'bg-sky-100 text-sky-900',
  emerald: 'bg-emerald-100 text-emerald-900',
  rose: 'bg-rose-100 text-rose-900',
  slate: 'bg-slate-100 text-slate-700',
} as const;

export function Badge({
  tone = 'slate',
  children,
}: {
  tone?: keyof typeof tones;
  children: ReactNode;
}) {
  return (
    <span
      className={cx(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}
