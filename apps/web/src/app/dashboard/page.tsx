'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import {
  claimInvoicePayment,
  getAtRiskFamilies,
  getBillingSummary,
  getFamilyBilling,
  getFamilyInvoices,
  createUnbilledTasks,
  getMonthReport,
  getUnbilledFamilies,
  runIngestion,
  sendDueSoonReminders,
  sendOverdueReminders,
  ApiError,
  type AtRiskFamily,
  type FamilyBilling,
  type FamilyInvoice,
  type MonthReport,
  type StaffBillingSummary,
  type UnbilledFamily,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import {
  FAMILY_INVOICE_LABELS,
  FAMILY_INVOICE_TONES,
  formatAmount,
  formatDate,
} from '@/lib/format';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { ExportCsvButton } from '@/components/ui/export-csv';
import { EmptyState } from '@/components/ui/empty-state';
import { MetricCard } from '@/components/ui/metric-card';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

function ParentInvoices({ familyId }: { familyId: string | null }) {
  const { notify } = useToast();
  const [invoices, setInvoices] = useState<FamilyInvoice[] | null>(null);
  const [billing, setBilling] = useState<FamilyBilling | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<string | null>(null);
  const [claimed, setClaimed] = useState<string[]>([]);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    getFamilyInvoices(token)
      .then(setInvoices)
      .catch(() => setError('No se pudieron cargar las facturas'));
    if (familyId) {
      getFamilyBilling(token, familyId)
        .then(setBilling)
        .catch(() => {});
    }
  }, [familyId]);

  if (error) return <p className="text-sm text-rose-700">{error}</p>;
  if (invoices === null) return <p className="text-sm text-muted">Cargando facturas...</p>;
  if (invoices.length === 0) {
    return (
      <EmptyState
        title="Todavía no hay facturas"
        description="Cuando el equipo publique una factura de tu familia, aparecerá aquí."
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {billing && Number(billing.outstanding_amount) > 0 && (
        <Card>
          <p className="text-sm text-muted">Pendiente de pago</p>
          <p className="mt-1 text-2xl font-semibold tabular">
            {formatAmount(billing.outstanding_amount, billing.currency)}
          </p>
          {billing.overdue_count > 0 && (
            <p className="mt-1 text-sm text-rose-700">
              {billing.overdue_count} vencida{billing.overdue_count === 1 ? '' : 's'} ·{' '}
              {formatAmount(billing.overdue_amount, billing.currency)}
            </p>
          )}
          {(billing.due_soon_count ?? 0) > 0 && (
            <p className="mt-1 text-sm text-amber-800">
              {billing.due_soon_count} vence(n) en 7 días ·{' '}
              {formatAmount(billing.due_soon_amount ?? '0', billing.currency)}
            </p>
          )}
        </Card>
      )}
      <ul className="flex flex-col gap-3">
        {invoices.map((invoice) => (
          <li key={invoice.id}>
            <Card className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm text-muted">{formatDate(invoice.issue_date)}</p>
                <p className="mt-1 text-lg font-semibold tabular">
                  {formatAmount(invoice.amount, invoice.currency)}
                </p>
                {invoice.due_date && (
                  <p className="mt-1 text-xs text-muted">Vence {formatDate(invoice.due_date)}</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={FAMILY_INVOICE_TONES[invoice.status] ?? 'slate'}>
                  {FAMILY_INVOICE_LABELS[invoice.status] ?? invoice.status}
                </Badge>
                <DownloadDocumentButton documentId={invoice.document_id} />
                {(invoice.status === 'sent' || invoice.status === 'overdue') &&
                  (claimed.includes(invoice.id) ? (
                    <span className="text-xs text-muted">Aviso enviado</span>
                  ) : (
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={claiming === invoice.id}
                      onClick={async () => {
                        const token = getStoredToken();
                        if (!token) return;
                        setClaiming(invoice.id);
                        try {
                          await claimInvoicePayment(token, invoice.id);
                          setClaimed((current) => [...current, invoice.id]);
                          notify('Avisamos al equipo. Cuando confirmen el cobro, pasará a pagada.');
                        } catch (err) {
                          notify(
                            err instanceof ApiError ? err.message : 'No se pudo registrar el aviso',
                            'error',
                          );
                        } finally {
                          setClaiming(null);
                        }
                      }}
                    >
                      {claiming === invoice.id ? 'Enviando...' : 'He pagado'}
                    </Button>
                  ))}
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StaffHome({ name }: { name: string }) {
  const { notify } = useToast();
  const [summary, setSummary] = useState<StaffBillingSummary | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskFamily[]>([]);
  const [unbilled, setUnbilled] = useState<UnbilledFamily[]>([]);
  const [report, setReport] = useState<MonthReport | null>(null);
  const [running, setRunning] = useState(false);
  const [reminding, setReminding] = useState(false);
  const [creatingTasks, setCreatingTasks] = useState(false);

  function reloadSummary() {
    const token = getStoredToken();
    if (!token) return;
    getBillingSummary(token)
      .then(setSummary)
      .catch(() => setSummary(null));
    getAtRiskFamilies(token)
      .then(setAtRisk)
      .catch(() => setAtRisk([]));
    getUnbilledFamilies(token)
      .then(setUnbilled)
      .catch(() => setUnbilled([]));
    getMonthReport(token)
      .then(setReport)
      .catch(() => setReport(null));
  }

  useEffect(reloadSummary, []);

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
      reloadSummary();
    } catch (err) {
      notify(
        err instanceof ApiError ? err.message : 'No se pudieron procesar los correos',
        'error',
      );
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title={`Hola, ${name}`}
        description="Equipo interno"
        actions={
          <>
            <Button
              variant="secondary"
              disabled={reminding}
              onClick={async () => {
                const token = getStoredToken();
                if (!token) return;
                setReminding(true);
                try {
                  const overdue = await sendOverdueReminders(token);
                  const soon = await sendDueSoonReminders(token);
                  const sent = overdue.sent + soon.sent;
                  notify(
                    sent === 0
                      ? 'No había vencimientos que recordar.'
                      : `Enviados ${sent} recordatorio(s) (vencidas y 7 días).`,
                  );
                } catch (err) {
                  notify(
                    err instanceof ApiError
                      ? err.message
                      : 'No se pudieron enviar los recordatorios',
                    'error',
                  );
                } finally {
                  setReminding(false);
                }
              }}
            >
              {reminding ? 'Enviando...' : 'Recordatorios de vencimiento'}
            </Button>
            <Button onClick={handleIngestion} disabled={running}>
              {running ? 'Procesando...' : 'Procesar correos de prueba'}
            </Button>
          </>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        <MetricCard
          label={`Esperado ${summary?.year_month ?? ''}`}
          value={summary ? formatAmount(summary.expected_amount, summary.currency) : '—'}
          hint="Suma de cuotas de contratos activos"
        />
        <MetricCard
          label="Cobrado este mes"
          value={summary ? formatAmount(summary.collected_amount, summary.currency) : '—'}
          href="/dashboard/invoices"
          tone="ok"
        />
        <MetricCard
          label="Deuda vencida"
          value={summary ? formatAmount(summary.overdue_amount, summary.currency) : '—'}
          href="/dashboard/invoices"
          hint={summary ? `${summary.overdue_count} factura(s)` : undefined}
          emphasis="hero"
          tone="debt"
        />
        <MetricCard
          label="Vencen en 7 días"
          value={summary ? formatAmount(summary.due_soon_amount, summary.currency) : '—'}
          href="/dashboard/invoices"
          hint={summary ? `${summary.due_soon_count} factura(s)` : undefined}
          tone="warn"
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        <MetricCard
          label="Pendientes de revisión"
          value={summary ? String(summary.pending_review_count) : '—'}
          href="/dashboard/invoices"
          emphasis="compact"
        />
        <MetricCard
          label="Familias en riesgo"
          value={summary ? String(summary.families_with_debt) : '—'}
          href="/dashboard/families"
          emphasis="compact"
        />
        <MetricCard
          label="Tareas pendientes"
          value={summary ? String(summary.pending_tasks) : '—'}
          href="/dashboard/tasks"
          emphasis="compact"
        />
        <MetricCard
          label="Correos fallidos"
          value={summary ? String(summary.failed_emails) : '—'}
          href="/dashboard/emails"
          emphasis="compact"
        />
      </div>
      {unbilled.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">Sin facturar este mes</h2>
            <Button
              variant="secondary"
              size="sm"
              disabled={creatingTasks}
              onClick={async () => {
                const token = getStoredToken();
                if (!token) return;
                setCreatingTasks(true);
                try {
                  const result = await createUnbilledTasks(token);
                  notify(
                    result.created === 0
                      ? 'Ya había tareas de facturación pendientes.'
                      : `Creadas ${result.created} tarea(s) de facturación.`,
                  );
                  reloadSummary();
                } catch (err) {
                  notify(
                    err instanceof ApiError ? err.message : 'No se pudieron crear las tareas',
                    'error',
                  );
                } finally {
                  setCreatingTasks(false);
                }
              }}
            >
              {creatingTasks ? 'Creando...' : 'Crear tareas de facturación'}
            </Button>
          </div>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {unbilled.map((family) => (
              <li key={family.id} className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  href={`/dashboard/families/${family.id}`}
                  className="text-brand hover:underline"
                >
                  {family.name}
                </Link>
                <span className="tabular">
                  {formatAmount(family.expected_amount, family.currency)}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {report && report.families.length > 0 && (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">Cierre {report.year_month}</h2>
            <ExportCsvButton kind="month-report" label="Exportar cierre" />
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="py-1 font-medium">Familia</th>
                  <th className="py-1 font-medium">Esperado</th>
                  <th className="py-1 font-medium">Cobrado</th>
                  <th className="py-1 font-medium">Deuda</th>
                  <th className="py-1 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {report.families.map((family) => (
                  <tr key={family.id} className="border-t border-line">
                    <td className="py-2">
                      <Link
                        href={`/dashboard/families/${family.id}`}
                        className="text-brand hover:underline"
                      >
                        {family.name}
                      </Link>
                    </td>
                    <td className="tabular">
                      {formatAmount(family.expected_amount, family.currency)}
                    </td>
                    <td className="tabular">
                      {formatAmount(family.collected_amount, family.currency)}
                    </td>
                    <td className="tabular">
                      {formatAmount(family.outstanding_amount, family.currency)}
                    </td>
                    <td>
                      {family.unbilled ? (
                        <span className="text-amber-800">Sin facturar</span>
                      ) : Number(family.overdue_amount) > 0 ? (
                        <span className="text-rose-700">Vencida</span>
                      ) : Number(family.outstanding_amount) > 0 ? (
                        <span>Pendiente</span>
                      ) : (
                        <span className="text-emerald-700">Al día</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {atRisk.length > 0 && (
        <Card>
          <h2 className="font-medium">Familias en riesgo</h2>
          <ul className="mt-3 flex flex-col gap-2 text-sm">
            {atRisk.map((family) => (
              <li key={family.id} className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  href={`/dashboard/families/${family.id}`}
                  className="text-brand hover:underline"
                >
                  {family.name}
                </Link>
                <span className="text-rose-700 tabular">
                  {formatAmount(family.overdue_amount)} · {family.overdue_count} vencida(s)
                  {family.pending_tasks > 0 ? ` · ${family.pending_tasks} tarea(s)` : ''}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <p className="text-xs text-muted">Atajo: Ctrl+K abre la paleta de comandos.</p>
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/dashboard/invoices" className="text-brand hover:underline">
          Ir a la cola de revisión
        </Link>
        <Link href="/dashboard/emails" className="text-brand hover:underline">
          Correos ingeridos
        </Link>
        <Link href="/dashboard/tasks" className="text-brand hover:underline">
          Tareas
        </Link>
        <Link href="/dashboard/credit-notes" className="text-brand hover:underline">
          Notas de crédito
        </Link>
        <Link href="/dashboard/suppliers" className="text-brand hover:underline">
          Facturas de proveedor
        </Link>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  if (user.role === 'parent') {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title={`Hola, ${user.name}`}
          description="Facturas de tu familia"
          actions={<ExportCsvButton label="Exportar mis facturas" />}
        />
        <ParentInvoices familyId={user.family_id} />
      </div>
    );
  }

  return <StaffHome name={user.name} />;
}
