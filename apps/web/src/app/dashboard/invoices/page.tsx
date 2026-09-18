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
  bulkUpdateFamilyInvoices,
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
import { Input, Select } from '@/components/ui/input';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { ExportCsvButton } from '@/components/ui/export-csv';
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
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkFamily, setBulkFamily] = useState('');
  const [query, setQuery] = useState('');
  const [onlyUnassigned, setOnlyUnassigned] = useState(false);
  const [onlyStale, setOnlyStale] = useState(false);
  const [focusFamilyId, setFocusFamilyId] = useState<string | null>(null);
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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setFocusFamilyId(params.get('family_id'));
  }, []);

  function toggleSelected(invoiceId: string) {
    setSelected((current) =>
      current.includes(invoiceId)
        ? current.filter((id) => id !== invoiceId)
        : [...current, invoiceId],
    );
  }

  async function runBulk(payload: { status?: FamilyInvoiceStatus; family_id?: string }) {
    const token = getStoredToken();
    if (!token || selected.length === 0) return;
    try {
      const result = await bulkUpdateFamilyInvoices(token, { ids: selected, ...payload });
      notify(
        result.failed.length
          ? `Actualizadas ${result.updated}. Fallaron ${result.failed.length}.`
          : `Actualizadas ${result.updated} factura(s).`,
      );
      setSelected([]);
      reload();
    } catch (err) {
      notify(
        err instanceof ApiError ? err.message : 'No se pudo aplicar el cambio masivo',
        'error',
      );
    }
  }

  async function moveTo(invoiceId: string, nextStatus: FamilyInvoiceStatus) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const current = invoices.find((invoice) => invoice.id === invoiceId);
    if (nextStatus !== 'pending_review' && current && !current.family_id) {
      notify('Asigna una familia antes de publicar la factura.', 'error');
      return;
    }
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
      if (result.failed.length > 0 && result.processed === 0) {
        notify(`Fallaron ${result.failed.length} correo(s).`, 'error');
      } else {
        notify(
          result.processed === 0
            ? 'No había correos nuevos que procesar.'
            : `Procesados ${result.processed} correo${result.processed === 1 ? '' : 's'}.`,
        );
      }
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

  const visibleInvoices = (invoices ?? []).filter((invoice) => {
    if (focusFamilyId && invoice.family_id !== focusFamilyId) return false;
    if (onlyUnassigned && invoice.family_id) return false;
    if (onlyStale && (invoice.days_in_queue ?? 0) < 7) return false;
    if (query.trim()) {
      const needle = query.trim().toLowerCase();
      const name = (invoice.family_name ?? 'sin asignar').toLowerCase();
      return name.includes(needle);
    }
    return true;
  });

  const activeInvoice = invoices?.find((invoice) => invoice.id === activeId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Cola de revisión"
        description="Asigna familia y publica. El padre no ve nada en pendiente de revisión."
        actions={
          <>
            <ExportCsvButton />
            <Button onClick={handleIngestion} disabled={running} variant="secondary">
              {running ? 'Procesando...' : 'Procesar correos de prueba'}
            </Button>
          </>
        }
      />
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {invoices && invoices.length > 0 && (
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <Input
              label="Filtrar por familia"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={onlyUnassigned}
              onChange={(event) => setOnlyUnassigned(event.target.checked)}
            />
            Sin asignar
          </label>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={onlyStale}
              onChange={(event) => setOnlyStale(event.target.checked)}
            />
            Más de 7 días en cola
          </label>
        </div>
      )}
      {selected.length > 0 && (
        <div className="flex flex-wrap items-end gap-2 rounded-xl border border-line bg-paper p-3">
          <p className="text-sm">{selected.length} seleccionada(s)</p>
          <Select
            label="Asignar familia"
            value={bulkFamily}
            onChange={(event) => setBulkFamily(event.target.value)}
          >
            <option value="">Elegir…</option>
            {families.map((family) => (
              <option key={family.id} value={family.id}>
                {family.name}
              </option>
            ))}
          </Select>
          <Button
            variant="secondary"
            disabled={!bulkFamily}
            onClick={() => runBulk({ family_id: bulkFamily })}
          >
            Asignar
          </Button>
          <Button variant="secondary" onClick={() => runBulk({ status: 'sent' })}>
            Publicar
          </Button>
          <Button variant="secondary" onClick={() => runBulk({ status: 'paid' })}>
            Marcar pagadas
          </Button>
          <Button variant="ghost" onClick={() => setSelected([])}>
            Cancelar
          </Button>
        </div>
      )}
      {invoices === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : invoices.length === 0 ? (
        <EmptyState
          title="No hay facturas todavía."
          description="Procesa correos de prueba o espera a que llegue el buzón."
        />
      ) : visibleInvoices.length === 0 ? (
        <EmptyState
          title="Ninguna factura coincide con el filtro."
          description="Quita filtros o cambia el texto."
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
                invoices={visibleInvoices.filter((invoice) => invoice.status === column.status)}
                families={families}
                selected={selected}
                onToggleSelected={toggleSelected}
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
  selected,
  onToggleSelected,
  onMove,
  onAssignFamily,
}: {
  column: { status: FamilyInvoiceStatus; label: string; accent: string };
  invoices: FamilyInvoice[];
  families: Family[];
  selected: string[];
  onToggleSelected: (invoiceId: string) => void;
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
              selected={selected.includes(invoice.id)}
              onToggleSelected={onToggleSelected}
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
  selected = false,
  onToggleSelected,
  onMove,
  onAssignFamily,
  dragging = false,
}: {
  invoice: FamilyInvoice;
  families: Family[];
  selected?: boolean;
  onToggleSelected?: (invoiceId: string) => void;
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
      className={cx(
        'flex gap-2 rounded-lg border border-line bg-paper text-sm shadow-sm',
        dragging ? 'rotate-2 shadow-md' : '',
        selected ? 'ring-2 ring-brand/40' : '',
      )}
    >
      {onToggleSelected ? (
        <label
          className="flex items-start pt-3 pl-3"
          onPointerDown={(event) => event.stopPropagation()}
        >
          <input
            type="checkbox"
            checked={selected}
            aria-label={`Seleccionar factura de ${invoice.family_name ?? 'sin asignar'}`}
            onChange={() => onToggleSelected(invoice.id)}
          />
        </label>
      ) : null}
      <div
        ref={setNodeRef}
        style={style}
        {...listeners}
        {...attributes}
        className="flex min-w-0 flex-1 cursor-grab flex-col gap-2 p-3 active:cursor-grabbing"
      >
        <p className="font-medium text-ink">{invoice.family_name ?? 'Sin asignar'}</p>
        {invoice.possible_duplicate && <Badge tone="rose">Posible duplicado</Badge>}
        {(invoice.days_in_queue ?? 0) >= 1 && (
          <Badge tone="amber">
            {invoice.days_in_queue} día{invoice.days_in_queue === 1 ? '' : 's'} en cola
          </Badge>
        )}
        {(invoice.days_overdue ?? 0) >= 1 && (
          <Badge tone="rose">
            {invoice.days_overdue} día{invoice.days_overdue === 1 ? '' : 's'} de retraso
          </Badge>
        )}
        <div className="flex items-center justify-between text-xs text-muted">
          <span className="tabular">{formatAmount(invoice.amount, invoice.currency)}</span>
          {invoice.confidence !== null && (
            <Badge tone="amber">{Math.round(invoice.confidence * 100)}% confianza</Badge>
          )}
        </div>
        <p className="text-xs text-muted">{formatDate(invoice.issue_date)}</p>
        <div onPointerDown={(event) => event.stopPropagation()}>
          <DownloadDocumentButton documentId={invoice.document_id} label="Descargar PDF" />
        </div>
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
    </div>
  );
}
