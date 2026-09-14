export function formatAmount(amount: string | null | undefined, currency = 'EUR'): string {
  if (amount == null || amount === '') return 'Importe pendiente';
  const value = Number(amount);
  if (Number.isNaN(value)) return 'Importe pendiente';
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency }).format(value);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return 'Fecha pendiente';
  const [year, month, day] = iso.split('-').map(Number);
  if (!year || !month || !day) return iso;
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(
    new Date(year, month - 1, day),
  );
}

export const FAMILY_INVOICE_LABELS: Record<string, string> = {
  pending_review: 'Pendiente de revisión',
  sent: 'Enviada',
  paid: 'Pagada',
  overdue: 'Vencida',
};

export const SUPPLIER_INVOICE_LABELS: Record<string, string> = {
  pending_review: 'Pendiente de revisión',
  approved: 'Aprobada',
  paid: 'Pagada',
};

export const FAMILY_INVOICE_TONES: Record<string, 'amber' | 'blue' | 'emerald' | 'rose' | 'slate'> =
  {
    pending_review: 'amber',
    sent: 'blue',
    paid: 'emerald',
    overdue: 'rose',
  };

export const SUPPLIER_INVOICE_TONES: Record<
  string,
  'amber' | 'blue' | 'emerald' | 'rose' | 'slate'
> = {
  pending_review: 'amber',
  approved: 'blue',
  paid: 'emerald',
};
