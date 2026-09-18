'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Money } from '@/components/ui/money';
import { Chip } from '@/components/ui/badge';
import { formatDate } from '@/lib/format';
import type { FamilyInvoice } from '@/lib/api';

export interface InvoiceFieldEdits {
  amount: string | null;
  issue_date: string | null;
  due_date: string | null;
}

/**
 * Corregir la extraccion dentro de la propia tarjeta (TASK-0127).
 *
 * El producto es «el parser extrae, el humano revisa», pero el humano no tenia
 * donde escribir: ni en la tarjeta, ni en la ficha, ni en ningun dialogo habia
 * un campo de importe o de fecha. Solo se podia publicar el error o dejarlo en
 * la cola para siempre.
 *
 * El formulario nace con lo que saco el extractor y se abre solo cuando hace
 * falta, para no estorbar en la factura que vino bien.
 */
export function InvoiceFieldsEditor({
  invoice,
  onSave,
}: {
  invoice: FamilyInvoice;
  onSave: (edits: InvoiceFieldEdits) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState(invoice.amount ?? '');
  const [issueDate, setIssueDate] = useState(invoice.issue_date ?? '');
  const [dueDate, setDueDate] = useState(invoice.due_date ?? '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAmount(invoice.amount ?? '');
    setIssueDate(invoice.issue_date ?? '');
    setDueDate(invoice.due_date ?? '');
  }, [invoice.amount, invoice.issue_date, invoice.due_date]);

  const incomplete = invoice.amount === null || invoice.issue_date === null;
  const lowConfidence = invoice.confidence !== null && invoice.confidence < 0.5;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSave({
        amount: amount.trim() === '' ? null : amount.trim(),
        issue_date: issueDate || null,
        due_date: dueDate || null,
      });
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setOpen(true)}
          aria-label={`Corregir datos de la factura de ${invoice.family_name ?? 'sin asignar'}`}
        >
          Corregir datos
        </Button>
        {incomplete ? <Chip tone="rose">Faltan datos</Chip> : null}
        {!incomplete && lowConfidence ? <Chip tone="amber">Revisar</Chip> : null}
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      onPointerDown={(event) => event.stopPropagation()}
      className="flex flex-col gap-2 rounded-lg border border-line bg-raised p-3"
    >
      <Input
        label="Importe"
        inputMode="decimal"
        placeholder="45.00"
        value={amount}
        onChange={(event) => setAmount(event.target.value)}
      />
      <Input
        label="Fecha de emisión"
        type="date"
        value={issueDate}
        onChange={(event) => setIssueDate(event.target.value)}
      />
      <Input
        label="Vencimiento"
        type="date"
        value={dueDate}
        onChange={(event) => setDueDate(event.target.value)}
      />
      {/* Lo que dijo el extractor queda a la vista mientras se corrige: es la
          referencia para saber si merece la pena fiarse de la proxima. */}
      <p className="text-2xs text-muted">
        Extraído:{' '}
        <Money amount={invoice.amount} currency={invoice.currency} size="quiet" align="left" /> ·{' '}
        {formatDate(invoice.issue_date)}
      </p>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? 'Guardando...' : 'Guardar'}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
          Descartar
        </Button>
      </div>
    </form>
  );
}
