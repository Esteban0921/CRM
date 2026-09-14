import type { ReactNode } from 'react';
import { cx } from '@/lib/cx';

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx('rounded-xl border border-line bg-paper p-5 shadow-sm', className)}>
      {children}
    </div>
  );
}
