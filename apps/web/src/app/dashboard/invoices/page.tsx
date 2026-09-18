'use client';

import { useCallback, useEffect, useState } from 'react';
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
  getFamilyInvoicePage,
  runIngestion,
  updateFamilyInvoice,
  ApiError,
  type Family,
  type FamilyInvoice,
  type FamilyInvoiceStatus,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatDate } from '@/lib/format';
import { cx } from '@/lib/cx';
import { Badge, Chip } from '@/components/ui/badge';
import {
  InvoiceFieldsEditor,
  type InvoiceFieldEdits,
} from '@/components/invoices/invoice-fields-editor';
import { FamilyPickerDialog } from '@/components/invoices/family-picker';
import { Money } from '@/components/ui/money';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { Input, Select } from '@/components/ui/input';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { ExportCsvButton } from '@/components/ui/export-csv';
import { useToast } from '@/components/ui/toast';

/** Tamano de pagina por columna. Con 50 cabe una sesion de revision entera
 *  sin que el tablero tenga que cargar el historico completo. */
const PAGE_SIZE = 50;

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
  const [totals, setTotals] = useState<Record<string, number>>({});
  const [loadingMore, setLoadingMore] = useState<FamilyInvoiceStatus | null>(null);
  const [pickerInvoice, setPickerInvoice] = useState<FamilyInvoice | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const reload = useCallback((familyId?: string | null) => {
    const token = getStoredToken();
    if (!token) return;
    // Una peticion por columna, acotada: antes se pedia la tabla entera y con
    // 2.068 facturas eran 13,6 segundos hasta ver la primera tarjeta
    // (TASK-0126).
    Promise.all(
      COLUMNS.map((column) =>
        getFamilyInvoicePage(token, {
          status: column.status,
          familyId: familyId ?? undefined,
          limit: PAGE_SIZE,
        }).then((page) => ({ status: column.status, page })),
      ),
    )
      .then((results) => {
        setInvoices(results.flatMap((result) => result.page.items));
        setTotals(Object.fromEntries(results.map((result) => [result.status, result.page.total])));
      })
      .catch(() => setError('No se pudieron cargar las facturas'));
    getFamilies(token)
      .then(setFamilies)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const familyId = params.get('family_id');
    setFocusFamilyId(familyId);
    reload(familyId);
  }, [reload]);

  async function loadMore(status: FamilyInvoiceStatus) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    setLoadingMore(status);
    try {
      const loaded = invoices.filter((invoice) => invoice.status === status).length;
      const page = await getFamilyInvoicePage(token, {
        status,
        familyId: focusFamilyId ?? undefined,
        limit: PAGE_SIZE,
        offset: loaded,
      });
      setInvoices((current) => {
        const known = new Set((current ?? []).map((invoice) => invoice.id));
        return [...(current ?? []), ...page.items.filter((invoice) => !known.has(invoice.id))];
      });
      setTotals((current) => ({ ...current, [status]: page.total }));
    } catch {
      notify('No se pudieron cargar mas facturas', 'error');
    } finally {
      setLoadingMore(null);
    }
  }

  function openFamilyPicker(invoice: FamilyInvoice) {
    setPickerInvoice(invoice);
  }

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
    // Misma regla que el backend (TASK-0101), aqui solo para no hacer ir y
    // volver: se publicaba sin aviso y el padre veia «Importe pendiente» en
    // negrita, con un total de deuda que ademas no la sumaba (TASK-0128).
    if (nextStatus !== 'pending_review' && current) {
      if (!current.family_id) {
        notify('Asigna una familia antes de publicar la factura.', 'error');
        return;
      }
      if (current.amount === null) {
        notify('Indica el importe antes de publicar: el padre verá «importe pendiente».', 'error');
        return;
      }
      if (current.issue_date === null) {
        notify('Indica la fecha de emisión antes de publicar.', 'error');
        return;
      }
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

  async function saveInvoiceFields(invoiceId: string, edits: InvoiceFieldEdits) {
    const token = getStoredToken();
    if (!token || !invoices) return;
    const previous = invoices;
    setInvoices(
      invoices.map((invoice) => (invoice.id === invoiceId ? { ...invoice, ...edits } : invoice)),
    );
    try {
      const saved = await updateFamilyInvoice(token, invoiceId, edits);
      setInvoices((current) =>
        (current ?? []).map((invoice) => (invoice.id === invoiceId ? saved : invoice)),
      );
      notify('Factura corregida');
    } catch (err) {
      setInvoices(previous);
      notify(err instanceof ApiError ? err.message : 'No se pudieron guardar los cambios', 'error');
    }
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
      {/* Un unico dialogo para todo el tablero, en vez de un <select> con
          todas las familias dentro de cada tarjeta (TASK-0126). */}
      <FamilyPickerDialog
        open={pickerInvoice !== null}
        families={families}
        currentFamilyId={pickerInvoice?.family_id ?? null}
        invoiceLabel={pickerInvoice?.family_name ?? 'Sin asignar'}
        onPick={(familyId) => {
          if (pickerInvoice) assignFamily(pickerInvoice.id, familyId);
          setPickerInvoice(null);
        }}
        onClose={() => setPickerInvoice(null)}
      />
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
                total={totals[column.status] ?? 0}
                loadingMore={loadingMore === column.status}
                onLoadMore={() => loadMore(column.status)}
                selected={selected}
                onToggleSelected={toggleSelected}
                onMove={moveTo}
                onOpenFamilyPicker={openFamilyPicker}
                onSaveFields={saveInvoiceFields}
              />
            ))}
          </div>
          <DragOverlay>
            {activeInvoice ? (
              <InvoiceCard
                invoice={activeInvoice}
                onMove={moveTo}
                onOpenFamilyPicker={openFamilyPicker}
                onSaveFields={saveInvoiceFields}
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
  total,
  loadingMore,
  onLoadMore,
  selected,
  onToggleSelected,
  onMove,
  onOpenFamilyPicker,
  onSaveFields,
}: {
  column: { status: FamilyInvoiceStatus; label: string; accent: string };
  invoices: FamilyInvoice[];
  total: number;
  loadingMore: boolean;
  onLoadMore: () => void;
  selected: string[];
  onToggleSelected: (invoiceId: string) => void;
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
  onOpenFamilyPicker: (invoice: FamilyInvoice) => void;
  onSaveFields: (invoiceId: string, edits: InvoiceFieldEdits) => Promise<void>;
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
        {/* El contador es el total del servidor, no el de lo que hay cargado:
            si no, una columna paginada mentiria sobre cuanto trabajo queda. */}
        <span className="tabular rounded-full bg-canvas px-2 text-xs text-muted">
          {invoices.length < total ? `${invoices.length} de ${total}` : total}
        </span>
      </div>
      {/* Altura acotada con scroll propio: el grid igualaba las alturas de las
          cuatro columnas, asi que una columna larga estiraba la pagina a
          443.093 px y dejaba las otras tres como un vacio blanco. */}
      <div className="flex max-h-[calc(100vh-20rem)] flex-col gap-2 overflow-y-auto">
        {invoices.length === 0 ? (
          <p className="px-1 text-xs text-muted">Sin facturas</p>
        ) : (
          invoices.map((invoice) => (
            <InvoiceCard
              key={invoice.id}
              invoice={invoice}
              selected={selected.includes(invoice.id)}
              onToggleSelected={onToggleSelected}
              onMove={onMove}
              onOpenFamilyPicker={onOpenFamilyPicker}
              onSaveFields={onSaveFields}
            />
          ))
        )}
        {invoices.length < total && (
          <Button variant="ghost" size="sm" onClick={onLoadMore} disabled={loadingMore}>
            {loadingMore ? 'Cargando...' : `Cargar más (${total - invoices.length})`}
          </Button>
        )}
      </div>
    </div>
  );
}

function InvoiceCard({
  invoice,
  selected = false,
  onToggleSelected,
  onMove,
  onOpenFamilyPicker,
  onSaveFields,
  dragging = false,
}: {
  invoice: FamilyInvoice;
  selected?: boolean;
  onToggleSelected?: (invoiceId: string) => void;
  onMove: (invoiceId: string, nextStatus: FamilyInvoiceStatus) => void;
  onOpenFamilyPicker: (invoice: FamilyInvoice) => void;
  onSaveFields: (invoiceId: string, edits: InvoiceFieldEdits) => Promise<void>;
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
        {/* El importe es el dato por el que se trabaja en una cola de cobro:
            sube a primer nivel y la familia pasa a ser su etiqueta (TASK-0145). */}
        <div className="flex items-baseline justify-between gap-2">
          <Money
            amount={invoice.amount}
            currency={invoice.currency}
            size="strong"
            align="left"
            tone={invoice.status === 'overdue' ? 'debt' : 'auto'}
          />
          <span className="text-xs text-muted">{formatDate(invoice.issue_date)}</span>
        </div>
        <p className="truncate text-sm font-medium text-ink-2">
          {invoice.family_name ?? 'Sin asignar'}
        </p>
        <div className="flex flex-wrap items-center gap-1.5">
          {invoice.possible_duplicate && <Badge tone="rose">Posible duplicado</Badge>}
          {(invoice.days_overdue ?? 0) >= 1 && (
            <Badge tone="rose">
              {invoice.days_overdue} día{invoice.days_overdue === 1 ? '' : 's'} de retraso
            </Badge>
          )}
          {/* Antiguedad y confianza son metadatos: contorno, para que dejen de
              competir con el estado y con el importe (TASK-0146). */}
          {(invoice.days_in_queue ?? 0) >= 1 && (
            <Chip tone={(invoice.days_in_queue ?? 0) >= 7 ? 'amber' : 'slate'}>
              {invoice.days_in_queue} día{invoice.days_in_queue === 1 ? '' : 's'} en cola
            </Chip>
          )}
          {invoice.confidence !== null && (
            <Chip tone={invoice.confidence < 0.5 ? 'amber' : 'slate'}>
              {Math.round(invoice.confidence * 100)}% confianza
            </Chip>
          )}
        </div>
        <div onPointerDown={(event) => event.stopPropagation()}>
          <DownloadDocumentButton documentId={invoice.document_id} label="Descargar PDF" />
        </div>
        <div onPointerDown={(event) => event.stopPropagation()}>
          <InvoiceFieldsEditor
            invoice={invoice}
            onSave={(edits) => onSaveFields(invoice.id, edits)}
          />
        </div>
        {/* Un boton, no un <select> con todas las familias dentro: ese select
            por tarjeta era el 80% de los nodos del DOM del tablero
            (TASK-0126). */}
        <div onPointerDown={(event) => event.stopPropagation()}>
          <Button
            variant="secondary"
            size="sm"
            className="w-full justify-between"
            aria-label={`Asignar familia de la factura de ${invoice.family_name ?? 'sin asignar'}`}
            onClick={() => onOpenFamilyPicker(invoice)}
          >
            <span className="truncate">{invoice.family_name ?? 'Sin asignar'}</span>
            <span aria-hidden className="text-muted">
              Cambiar
            </span>
          </Button>
        </div>
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
