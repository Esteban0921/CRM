'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { getFamilyInvoices, type FamilyInvoice } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';

const STATUS_LABELS: Record<string, string> = {
  pending_review: 'En revisión',
  sent: 'Enviada',
  paid: 'Pagada',
  overdue: 'Vencida',
};

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

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (invoices === null) return <p className="text-sm text-neutral-500">Cargando facturas...</p>;
  if (invoices.length === 0)
    return <p className="text-sm text-neutral-500">Todavía no hay facturas.</p>;

  return (
    <ul className="flex flex-col gap-2">
      {invoices.map((invoice) => (
        <li key={invoice.id} className="rounded border border-neutral-200 p-3 text-sm">
          <div className="flex justify-between">
            <span>{invoice.issue_date ?? 'Fecha pendiente de confirmar'}</span>
            <span className="font-medium">
              {invoice.amount ? `${invoice.amount} ${invoice.currency}` : 'Importe pendiente'}
            </span>
          </div>
          <span className="text-xs text-neutral-500">
            {STATUS_LABELS[invoice.status] ?? invoice.status}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  if (user.role === 'parent') {
    return (
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-xl font-semibold">Hola, {user.name}</h1>
          <p className="text-sm text-neutral-500">Facturas de tu familia</p>
        </div>
        <ParentInvoices />
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Hola, {user.name}</h1>
      <p className="text-sm text-neutral-500">Equipo interno</p>
      <Link href="/dashboard/invoices" className="mt-4 inline-block text-sm underline">
        Ir a la cola de revisión de facturas
      </Link>
    </div>
  );
}
