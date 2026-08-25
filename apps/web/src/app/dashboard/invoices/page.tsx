'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth-context';
import { getFamilyInvoices, updateFamilyInvoice, type FamilyInvoice } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';

export default function InvoiceReviewQueuePage() {
  const { user, loading: authLoading } = useAuth();
  const [invoices, setInvoices] = useState<FamilyInvoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getFamilyInvoices(token, 'pending_review')
      .then(setInvoices)
      .catch(() => setError('No se pudieron cargar las facturas'));
  }

  useEffect(reload, []);

  async function markAsSent(invoiceId: string) {
    const token = getStoredToken();
    if (!token) return;
    try {
      await updateFamilyInvoice(token, invoiceId, { status: 'sent' });
      reload();
    } catch {
      setError('No se pudo actualizar la factura');
    }
  }

  if (authLoading) return null;
  if (user && user.role === 'parent') {
    return <p className="text-sm text-red-600">No tienes acceso a esta página.</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Cola de revisión</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {invoices === null ? (
        <p className="text-sm text-neutral-500">Cargando...</p>
      ) : invoices.length === 0 ? (
        <p className="text-sm text-neutral-500">No hay facturas pendientes de revisión.</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-neutral-200 text-neutral-500">
              <th className="py-2">Familia</th>
              <th className="py-2">Importe</th>
              <th className="py-2">Confianza</th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id} className="border-b border-neutral-100">
                <td className="py-2">{invoice.family_id ?? 'Sin enlazar'}</td>
                <td className="py-2">
                  {invoice.amount ? `${invoice.amount} ${invoice.currency}` : '—'}
                </td>
                <td className="py-2">
                  {invoice.confidence !== null ? `${Math.round(invoice.confidence * 100)}%` : '—'}
                </td>
                <td className="py-2">
                  <button
                    onClick={() => markAsSent(invoice.id)}
                    className="rounded bg-neutral-900 px-3 py-1 text-white"
                  >
                    Marcar revisada
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
