'use client';

import { useEffect, useState } from 'react';
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
  getFamilyInvoices,
  updateFamilyInvoice,
  type FamilyInvoice,
  type FamilyInvoiceStatus,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';

const COLUMNS: { status: FamilyInvoiceStatus; label: string; accent: string }[] = [
  { status: 'pending_review', label: 'Pendiente de revisión', accent: 'border-t-amber-400' },
  { status: 'sent', label: 'Enviada', accent: 'border-t-blue-400' },
  { status: 'paid', label: 'Pagada', accent: 'border-t-emerald-400' },
  { status: 'overdue', label: 'Vencida', accent: 'border-t-red-400' },
];

export default function InvoiceReviewQueuePage() {
  const { user, loading: authLoading } = useAuth();
  const [invoices, setInvoices] = useState<FamilyInvoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
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

  if (authLoading) return null;
  if (user && user.role === 'parent') {
    return <p className="text-sm text-red-600">No tienes acceso a esta página.</p>;
  }

  const activeInvoice = invoices?.find((invoice) => invoice.id === activeId) ?? null;

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Cola de revisión</h1>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {invoices === null ? (
        <p className="text-sm text-neutral-500">Cargando...</p>
      ) : invoices.length === 0 ? (
        <p className="text-sm text-neutral-500">No hay facturas todavía.</p>
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
                onMove={moveTo}
              />
            ))}
          </div>
          <DragOverlay>
            {activeInvoice ? (
              <InvoiceCard invoice={activeInvoice} onMove={moveTo} dragging />
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
  onMove,
}: {
  column: { status: FamilyInvoiceStatus; label: string; accent: string };
  invoices: FamilyInvoice[];
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: column.status });

  return (
    <div
      ref={setNodeRef}
      className={`flex min-h-[12rem] flex-col gap-2 rounded-lg border-t-4 bg-neutral-50 p-3 transition-colors ${column.accent} ${isOver ? 'bg-neutral-100' : ''}`}
    >
      <div className="flex items-center justify-between px-1">
        <h2 className="text-sm font-medium text-neutral-700">{column.label}</h2>
        <span className="rounded-full bg-neutral-200 px-2 text-xs text-neutral-600">
          {invoices.length}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {invoices.length === 0 ? (
          <p className="px-1 text-xs text-neutral-400">Sin facturas</p>
        ) : (
          invoices.map((invoice) => (
            <InvoiceCard key={invoice.id} invoice={invoice} onMove={onMove} />
          ))
        )}
      </div>
    </div>
  );
}

function InvoiceCard({
  invoice,
  onMove,
  dragging = false,
}: {
  invoice: FamilyInvoice;
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
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
      className={`flex cursor-grab flex-col gap-2 rounded-md border border-neutral-200 bg-white p-3 text-sm shadow-sm active:cursor-grabbing ${dragging ? 'rotate-2 shadow-md' : ''}`}
    >
      <p className="font-medium text-neutral-900">{invoice.family_name ?? 'Sin enlazar'}</p>
      <div className="flex items-center justify-between text-xs text-neutral-500">
        <span>
          {invoice.amount ? `${invoice.amount} ${invoice.currency}` : 'Importe pendiente'}
        </span>
        {invoice.confidence !== null && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
            {Math.round(invoice.confidence * 100)}% confianza
          </span>
        )}
      </div>
      {invoice.due_date && <p className="text-xs text-neutral-400">Vence: {invoice.due_date}</p>}
      <select
        aria-label={`Cambiar estado de la factura de ${invoice.family_name ?? 'sin enlazar'}`}
        value={invoice.status}
        onChange={(event) => onMove(invoice.id, event.target.value as FamilyInvoiceStatus)}
        onPointerDown={(event) => event.stopPropagation()}
        className="rounded border border-neutral-200 bg-neutral-50 px-1.5 py-1 text-xs"
      >
        {COLUMNS.map((column) => (
          <option key={column.status} value={column.status}>
            {column.label}
          </option>
        ))}
      </select>
    </div>
  );
}
