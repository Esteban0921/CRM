'use client';

import { useState } from 'react';
import {
  downloadFamilyInvoicesCsv,
  downloadMonthReportCsv,
  ApiError,
  type FamilyInvoiceStatus,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { Button } from './button';

export function ExportCsvButton({
  status,
  label = 'Exportar CSV',
  kind = 'invoices',
}: {
  status?: FamilyInvoiceStatus;
  label?: string;
  kind?: 'invoices' | 'month-report';
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    const token = getStoredToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      const { blob, filename } =
        kind === 'month-report'
          ? await downloadMonthReportCsv(token)
          : await downloadFamilyInvoicesCsv(token, status);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo exportar');
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex flex-col gap-1">
      <Button variant="secondary" onClick={handleClick} disabled={busy}>
        {busy ? 'Exportando...' : label}
      </Button>
      {error && <span className="text-xs text-rose-700">{error}</span>}
    </span>
  );
}
