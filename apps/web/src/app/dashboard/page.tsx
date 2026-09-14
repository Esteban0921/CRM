'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import {
  getFamilies,
  getFamilyInvoices,
  runIngestion,
  ApiError,
  type FamilyInvoice,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import {
  FAMILY_INVOICE_LABELS,
  FAMILY_INVOICE_TONES,
  formatAmount,
  formatDate,
} from '@/lib/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { MetricCard } from '@/components/ui/metric-card';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

function ParentInvoices() {
  const [invoices, setInvoices] = useState<FamilyInvoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    getFamilyInvoices(token)
      .then(setInvoices)
      .catch(() => setError('No se pudieron cargar las facturas'));
  }, []);

  if (error) return <p className="text-sm text-rose-700">{error}</p>;
  if (invoices === null) return <p className="text-sm text-muted">Cargando facturas...</p>;
  if (invoices.length === 0) {
    return (
      <EmptyState
        title="Todavía no hay facturas"
        description="Cuando el equipo publique una factura de tu familia, aparecerá aquí."
      />
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {invoices.map((invoice) => (
        <li key={invoice.id}>
          <Card className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-muted">{formatDate(invoice.issue_date)}</p>
              <p className="mt-1 text-lg font-semibold tabular">
                {formatAmount(invoice.amount, invoice.currency)}
              </p>
            </div>
            <Badge tone={FAMILY_INVOICE_TONES[invoice.status] ?? 'slate'}>
              {FAMILY_INVOICE_LABELS[invoice.status] ?? invoice.status}
            </Badge>
          </Card>
        </li>
      ))}
    </ul>
  );
}

function StaffHome({ name }: { name: string }) {
  const { notify } = useToast();
  const [pending, setPending] = useState<number | null>(null);
  const [overdue, setOverdue] = useState<number | null>(null);
  const [families, setFamilies] = useState<number | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    getFamilyInvoices(token, 'pending_review')
      .then((rows) => setPending(rows.length))
      .catch(() => setPending(null));
    getFamilyInvoices(token, 'overdue')
      .then((rows) => setOverdue(rows.length))
      .catch(() => setOverdue(null));
    getFamilies(token)
      .then((rows) => setFamilies(rows.length))
      .catch(() => setFamilies(null));
  }, []);

  async function handleIngestion() {
    const token = getStoredToken();
    if (!token) return;
    setRunning(true);
    try {
      const result = await runIngestion(token);
      notify(
        result.processed === 0
          ? 'No había correos nuevos que procesar.'
          : `Procesados ${result.processed} correo${result.processed === 1 ? '' : 's'}.`,
      );
      const pendingRows = await getFamilyInvoices(token, 'pending_review');
      setPending(pendingRows.length);
    } catch (err) {
      notify(
        err instanceof ApiError ? err.message : 'No se pudieron procesar los correos',
        'error',
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={`Hola, ${name}`}
        description="Equipo interno"
        actions={
          <Button onClick={handleIngestion} disabled={running}>
            {running ? 'Procesando...' : 'Procesar correos de prueba'}
          </Button>
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Pendientes de revisión"
          value={pending === null ? '—' : String(pending)}
          href="/dashboard/invoices"
          hint="Facturas a familias que aún no se publican"
        />
        <MetricCard
          label="Vencidas"
          value={overdue === null ? '—' : String(overdue)}
          href="/dashboard/invoices"
        />
        <MetricCard
          label="Familias"
          value={families === null ? '—' : String(families)}
          href="/dashboard/families"
        />
      </div>
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/dashboard/invoices" className="text-brand hover:underline">
          Ir a la cola de revisión
        </Link>
        <Link href="/dashboard/suppliers" className="text-brand hover:underline">
          Facturas de proveedor
        </Link>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  if (user.role === 'parent') {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader title={`Hola, ${user.name}`} description="Facturas de tu familia" />
        <ParentInvoices />
      </div>
    );
  }

  return <StaffHome name={user.name} />;
}
