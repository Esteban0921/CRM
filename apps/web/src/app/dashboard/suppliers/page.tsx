'use client';

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  createSupplier,
  getSupplierInvoices,
  getSuppliers,
  updateSupplierInvoice,
  ApiError,
  type Supplier,
  type SupplierCategory,
  type SupplierInvoice,
  type SupplierInvoiceStatus,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatAmount, formatDate } from '@/lib/format';
import { cx } from '@/lib/cx';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { EmptyState } from '@/components/ui/empty-state';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

const COLUMNS: { status: SupplierInvoiceStatus; label: string; accent: string }[] = [
  { status: 'pending_review', label: 'Pendiente de revisión', accent: 'border-t-amber-400' },
  { status: 'approved', label: 'Aprobada', accent: 'border-t-sky-400' },
  { status: 'paid', label: 'Pagada', accent: 'border-t-emerald-400' },
];

const CATEGORY_LABELS: Record<string, string> = {
  fuel: 'Combustible',
  maintenance: 'Mantenimiento',
  insurance: 'Seguro',
  other: 'Otro',
};

export default function SupplierInvoicesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { notify } = useToast();
  const [invoices, setInvoices] = useState<SupplierInvoice[] | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [category, setCategory] = useState<SupplierCategory>('other');
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getSupplierInvoices(token)
      .then(setInvoices)
      .catch(() => setError('No se pudieron cargar las facturas de proveedor'));
    getSuppliers(token)
      .then(setSuppliers)
      .catch(() => {});
  }

  useEffect(reload, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    setSubmitting(true);
    try {
      await createSupplier(token, { name, email: email || undefined, category });
      setName('');
      setEmail('');
      setCategory('other');
      setOpen(false);
      notify('Proveedor creado');
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear el proveedor');
    } finally {
      setSubmitting(false);
    }
  }

  async function moveTo(invoiceId: string, nextStatus: SupplierInvoiceStatus) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const previous = invoices;
    setInvoices(
      invoices.map((invoice) =>
        invoice.id === invoiceId ? { ...invoice, status: nextStatus } : invoice,
      ),
    );
    try {
      await updateSupplierInvoice(token, invoiceId, { status: nextStatus });
    } catch {
      setError('No se pudo mover la factura');
      setInvoices(previous);
    }
  }

  async function assignSupplier(invoiceId: string, supplierId: string | null) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const previous = invoices;
    const supplierName = suppliers.find((supplier) => supplier.id === supplierId)?.name ?? null;
    setInvoices(
      invoices.map((invoice) =>
        invoice.id === invoiceId
          ? { ...invoice, supplier_id: supplierId, supplier_name: supplierName }
          : invoice,
      ),
    );
    try {
      await updateSupplierInvoice(token, invoiceId, { supplier_id: supplierId });
    } catch {
      setError('No se pudo asignar el proveedor');
      setInvoices(previous);
    }
  }

  if (loading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Facturas de proveedor"
        description="Gastos internos: combustible, taller, seguros. El padre no ve este tablero."
        actions={<Button onClick={() => setOpen(true)}>Nuevo proveedor</Button>}
      />
      <Dialog open={open} title="Nuevo proveedor" onClose={() => setOpen(false)}>
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <Input
            label="Nombre"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <Input
            label="Email (para clasificar el buzón)"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Select
            label="Categoría"
            value={category}
            onChange={(event) => setCategory(event.target.value as SupplierCategory)}
          >
            <option value="fuel">Combustible</option>
            <option value="maintenance">Mantenimiento</option>
            <option value="insurance">Seguro</option>
            <option value="other">Otro</option>
          </Select>
          <Button type="submit" disabled={submitting}>
            Añadir proveedor
          </Button>
        </form>
      </Dialog>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {invoices === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : invoices.length === 0 ? (
        <EmptyState
          title="No hay facturas de proveedor todavía."
          description="Cuando la ingesta clasifique un correo de un proveedor conocido, aparecerá aquí."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {COLUMNS.map((column) => (
            <section
              key={column.status}
              className={cx(
                'flex min-h-[12rem] flex-col gap-2 rounded-xl border-t-4 bg-paper p-3 shadow-sm',
                column.accent,
              )}
            >
              <div className="flex items-center justify-between px-1">
                <h2 className="text-sm font-medium text-ink">{column.label}</h2>
                <span className="rounded-full bg-canvas px-2 text-xs text-muted">
                  {invoices.filter((invoice) => invoice.status === column.status).length}
                </span>
              </div>
              {invoices
                .filter((invoice) => invoice.status === column.status)
                .map((invoice) => (
                  <article
                    key={invoice.id}
                    className="flex flex-col gap-2 rounded-lg border border-line bg-paper p-3 text-sm"
                  >
                    <p className="font-medium text-ink">
                      {invoice.supplier_name ?? 'Proveedor sin asignar'}
                    </p>
                    <p className="tabular text-xs text-muted">
                      {formatAmount(invoice.amount, invoice.currency)} ·{' '}
                      {formatDate(invoice.issue_date)}
                    </p>
                    <Badge tone="slate">
                      {CATEGORY_LABELS[invoice.category] ?? invoice.category}
                    </Badge>
                    <DownloadDocumentButton
                      documentId={invoice.document_id}
                      label="Descargar PDF"
                    />
                    {suppliers.length > 0 && (
                      <Select
                        aria-label={`Asignar proveedor de ${invoice.supplier_name ?? 'factura'}`}
                        value={invoice.supplier_id ?? ''}
                        onChange={(event) => assignSupplier(invoice.id, event.target.value || null)}
                      >
                        <option value="">Sin asignar</option>
                        {suppliers.map((supplier) => (
                          <option key={supplier.id} value={supplier.id}>
                            {supplier.name}
                          </option>
                        ))}
                      </Select>
                    )}
                    <Select
                      aria-label={`Cambiar estado de ${invoice.supplier_name ?? 'factura de proveedor'}`}
                      value={invoice.status}
                      onChange={(event) =>
                        moveTo(invoice.id, event.target.value as SupplierInvoiceStatus)
                      }
                    >
                      {COLUMNS.map((item) => (
                        <option key={item.status} value={item.status}>
                          {item.label}
                        </option>
                      ))}
                    </Select>
                  </article>
                ))}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
