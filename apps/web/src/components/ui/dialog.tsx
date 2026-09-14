'use client';

import type { ReactNode } from 'react';
import { Button } from './button';

export function Dialog({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-ink/40"
        aria-label="Cerrar"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="relative z-10 w-full max-w-md rounded-xl border border-line bg-paper p-5 shadow-lg"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 id="dialog-title" className="text-lg font-semibold text-ink">
            {title}
          </h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Cerrar
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}
