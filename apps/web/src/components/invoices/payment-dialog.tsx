'use client';

import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Input, Select } from '@/components/ui/input';
import { Money } from '@/components/ui/money';
import { addPayment, ApiError, type FamilyInvoice, type PaymentMethod } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { useToast } from '@/components/ui/toast';

const METHODS: { value: PaymentMethod; label: string }[] = [
  { value: 'transfer', label: 'Transferencia' },
  { value: 'direct_debit', label: 'Domiciliación' },
  { value: 'card', label: 'Tarjeta' },
  { value: 'cash', label: 'Efectivo' },
  { value: 'other', label: 'Otro' },
];

function outstandingOf(invoice: FamilyInvoice): string {
  const total = Number(invoice.amount ?? 0);
  const paid = Number(invoice.paid_amount ?? 0);
  const resto = total - paid;
  return (resto > 0 ? resto : 0).toFixed(2);
}

/**
 * Hoy en la hora local, no en UTC: `toISOString()` da la fecha UTC, y entre
 * las 00:00 y las 02:00 en Espana precargaba AYER, con lo que un cobro del
 * dia 1 caia en el cierre del mes anterior (TASK-0102).
 */
function localToday(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Registrar un cobro, total o parcial (TASK-0157).
 *
 * Hasta ahora la unica forma de decir que una familia habia pagado era mover
 * la factura a «pagada», sin fecha de cobro ni importe: no se podia expresar
 * «ha pagado 60 de 150», y el cierre del mes se calculaba por fecha de
 * emision, con lo que un cobro de septiembre sobre una factura de agosto no
 * aparecia en ningun mes.
 */
export function PaymentDialog({
  invoice,
  open,
  onClose,
  onRecorded,
}: {
  invoice: FamilyInvoice | null;
  open: boolean;
  onClose: () => void;
  onRecorded: () => void;
}) {
  const { notify } = useToast();
  const [amount, setAmount] = useState('');
  const [paidOn, setPaidOn] = useState('');
  const [method, setMethod] = useState<PaymentMethod>('transfer');
  const [reference, setReference] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open || !invoice) return;
    // Precargado con lo que queda: el caso normal es cobrar el resto entero,
    // y el parcial es escribir menos.
    setAmount(outstandingOf(invoice));
    setPaidOn(localToday());
    setMethod('transfer');
    setReference('');
  }, [open, invoice]);

  if (!invoice) return null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token || !invoice) return;
    setSaving(true);
    try {
      await addPayment(token, invoice.id, {
        amount,
        paid_on: paidOn || undefined,
        method,
        reference: reference || undefined,
      });
      notify('Cobro registrado');
      onRecorded();
      onClose();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'No se pudo registrar el cobro', 'error');
    } finally {
      setSaving(false);
    }
  }

  const pendiente = outstandingOf(invoice);
  const yaCobrado = Number(invoice.paid_amount ?? 0) > 0;

  return (
    <Dialog open={open} title="Registrar cobro" onClose={onClose} size="sm">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex items-baseline justify-between rounded-lg bg-canvas px-3 py-2">
          <span className="text-sm text-muted">Pendiente</span>
          <Money amount={pendiente} currency={invoice.currency} size="strong" />
        </div>
        {yaCobrado ? (
          <p className="text-xs text-muted">
            Ya cobrado:{' '}
            <Money
              amount={invoice.paid_amount}
              currency={invoice.currency}
              size="quiet"
              align="left"
            />{' '}
            de{' '}
            <Money amount={invoice.amount} currency={invoice.currency} size="quiet" align="left" />
          </p>
        ) : null}
        <Input
          label="Importe cobrado"
          inputMode="decimal"
          required
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        <Input
          label="Fecha del cobro"
          type="date"
          required
          value={paidOn}
          onChange={(event) => setPaidOn(event.target.value)}
        />
        <Select
          label="Método"
          value={method}
          onChange={(event) => setMethod(event.target.value as PaymentMethod)}
        >
          {METHODS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </Select>
        <Input
          label="Referencia (opcional)"
          placeholder="Nº de transferencia, recibo…"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
        <Button type="submit" disabled={saving}>
          {saving ? 'Guardando...' : 'Registrar cobro'}
        </Button>
      </form>
    </Dialog>
  );
}
