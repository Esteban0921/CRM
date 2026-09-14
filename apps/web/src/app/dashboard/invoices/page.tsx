'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core';
import { useAuth } from '@/lib/auth-context';
import {
  getFamilies,
  getFamilyInvoices,
  runIngestion,
  updateFamilyInvoice,
  ApiError,
  type Family,
  type FamilyInvoice,
  type FamilyInvoiceStatus,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatAmount, formatDate } from '@/lib/format';
import { cx } from '@/lib/cx';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { Select } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';

const COLUMNS: { status: FamilyInvoiceStatus; label: string; accent: string }[] = [
  { status: 'pending_review', label: 'Pendiente de revisión', accent: 'border-t-amber-400' },
  { status: 'sent', label: 'Enviada', accent: 'border-t-sky-400' },
  { status: 'paid', label: 'Pagada', accent: 'border-t-emerald-400' },
  { status: 'overdue', label: 'Vencida', accent: 'border-t-rose-400' },
];

export default function InvoiceReviewQueuePage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { notify } = useToast();
  const [invoices, setInvoices] = useState<FamilyInvoice[] | null>(null);
  const [families, setFamilies] = useState<Family[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getFamilyInvoices(token)
      .then(setInvoices)
      .catch(() => setError('No se pudieron cargar las facturas'));
    getFamilies(token)
      .then(setFamilies)
      .catch(() => {});
  }

  useEffect(reload, []);

  async function moveTo(invoiceId: string, nextStatus: FamilyInvoiceStatus) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const previous = invoices;
    setInvoices(
      invoices.map((invoice) =>
        invoice.id === invoiceId ? { ...invoice, status: nextStatus } : invoice,
      ),
    );
    try {
      await updateFamilyInvoice(token, invoiceId, { status: nextStatus });
    } catch {
      setError('No se pudo mover la factura');
      setInvoices(previous);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;
    const invoice = invoices?.find((candidate) => candidate.id === active.id);
    const nextStatus = over.id as FamilyInvoiceStatus;
    if (!invoice || invoice.status === nextStatus) return;
    moveTo(invoice.id, nextStatus);
  }

  async function assignFamily(invoiceId: string, familyId: string | null) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const previous = invoices;
    const familyName = families.find((family) => family.id === familyId)?.name ?? null;
    setInvoices(
      invoices.map((invoice) =>
        invoice.id === invoiceId
          ? { ...invoice, family_id: familyId, family_name: familyName }
          : invoice,
      ),
    );
    try {
      await updateFamilyInvoice(token, invoiceId, { family_id: familyId });
    } catch {
      setError('No se pudo asignar la familia');
      setInvoices(previous);
    }
  }

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
      reload();
    } catch (err) {
      notify(
        err instanceof ApiError ? err.message : 'No se pudieron procesar los correos',
        'error',
      );
    } finally {
      setRunning(false);
    }
  }

  if (authLoading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  const activeInvoice = invoices?.find((invoice) => invoice.id === activeId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Cola de revisión"
        description="Asigna familia y publica. El padre no ve nada en pendiente de revisión."
        actions={
          <Button onClick={handleIngestion} disabled={running} variant="secondary">
            {running ? 'Procesando...' : 'Procesar correos de prueba'}
          </Button>
        }
      />
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {invoices === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : invoices.length === 0 ? (
        <EmptyState
          title="No hay facturas todavía."
          description="Procesa correos de prueba o espera a que llegue el buzón."
        />
      ) : (
        <DndContext
          sensors={sensors}
          onDragStart={(event: DragStartEvent) => setActiveId(String(event.active.id))}
          onDragEnd={handleDragEnd}
          onDragCancel={() => setActiveId(null)}
        >
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            {COLUMNS.map((column) => (
              <Column
                key={column.status}
                column={column}
                invoices={invoices.filter((invoice) => invoice.status === column.status)}
                families={families}
                onMove={moveTo}
                onAssignFamily={assignFamily}
              />
            ))}
          </div>
          <DragOverlay>
            {activeInvoice ? (
              <InvoiceCard
                invoice={activeInvoice}
                families={families}
                onMove={moveTo}
                onAssignFamily={assignFamily}
                dragging
              />
            ) : null}
          </DragOverlay>
        </DndContext>
      )}
    </div>
  );
}

function Column({
  column,
  invoices,
  families,
  onMove,
  onAssignFamily,
}: {
  column: { status: FamilyInvoiceStatus; label: string; accent: string };
  invoices: FamilyInvoice[];
  families: Family[];
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
  onAssignFamily: (invoiceId: string, familyId: string | null) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.status });

  return (
    <div
      ref={setNodeRef}
      className={cx(
        'flex min-h-[12rem] flex-col gap-2 rounded-xl border-t-4 bg-paper p-3 shadow-sm transition-colors',
        column.accent,
        isOver ? 'bg-canvas' : '',
      )}
    >
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-medium text-ink">{column.label}</h2>
        <span className="rounded-full bg-canvas px-2 text-xs text-muted">{invoices.length}</span>
      </div>
      <div className="flex flex-col gap-2">
        {invoices.length === 0 ? (
          <p className="px-1 text-xs text-muted">Sin facturas</p>
        ) : (
          invoices.map((invoice) => (
            <InvoiceCard
              key={invoice.id}
              invoice={invoice}
              families={families}
              onMove={onMove}
              onAssignFamily={onAssignFamily}
            />
          ))
        )}
      </div>
    </div>
  );
}

function InvoiceCard({
  invoice,
  families,
  onMove,
  onAssignFamily,
  dragging = false,
}: {
  invoice: FamilyInvoice;
  families: Family[];
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
  onAssignFamily: (invoiceId: string, familyId: string | null) => void;
  dragging?: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: invoice.id });
  const style = transform
    ? { transform: `translate(${transform.x}px, ${transform.y}px)` }
    : undefined;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={cx(
        'flex cursor-grab flex-col gap-2 rounded-lg border border-line bg-paper p-3 text-sm shadow-sm active:cursor-grabbing',
        dragging ? 'rotate-2 shadow-md' : '',
      )}
    >
      <p className="font-medium text-ink">{invoice.family_name ?? 'Sin asignar'}</p>
      <div className="flex items-center justify-between text-xs text-muted">
        <span className="tabular">{formatAmount(invoice.amount, invoice.currency)}</span>
        {invoice.confidence !== null && (
          <Badge tone="amber">{Math.round(invoice.confidence * 100)}% confianza</Badge>
        )}
      </div>
      <p className="text-xs text-muted">{formatDate(invoice.issue_date)}</p>
      <Select
        aria-label={`Asignar familia de la factura de ${invoice.family_name ?? 'sin asignar'}`}
        value={invoice.family_id ?? ''}
        onChange={(event) => onAssignFamily(invoice.id, event.target.value || null)}
        onPointerDown={(event) => event.stopPropagation()}
      >
        <option value="">Sin asignar</option>
        {families.map((family) => (
          <option key={family.id} value={family.id}>
            {family.name}
          </option>
        ))}
      </Select>
      <Select
        aria-label={`Cambiar estado de la factura de ${invoice.family_name ?? 'sin asignar'}`}
        value={invoice.status}
        onChange={(event) => onMove(invoice.id, event.target.value as FamilyInvoiceStatus)}
        onPointerDown={(event) => event.stopPropagation()}
      >
        {COLUMNS.map((column) => (
          <option key={column.status} value={column.status}>
            {column.label}
          </option>
        ))}
      </Select>
    </div>
  );
}
