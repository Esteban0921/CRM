'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  PAYMENT_CLAIM_TITLE,
  confirmInvoicePayment,
  getTasks,
  invoiceIdFromClaim,
  updateTask,
  ApiError,
  type Task,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatDate } from '@/lib/format';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

export default function TasksInboxPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const { notify } = useToast();
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getTasks(token)
      .then(setTasks)
      .catch(() => setError('No se pudieron cargar las tareas'));
  }

  useEffect(reload, []);

  if (loading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  const pending = tasks?.filter((task) => task.status === 'pending') ?? [];
  const done = tasks?.filter((task) => task.status === 'done') ?? [];

  async function toggle(task: Task) {
    const token = getStoredToken();
    if (!token) return;
    await updateTask(token, task.id, { status: task.status === 'done' ? 'pending' : 'done' });
    reload();
  }

  async function confirmClaim(task: Task) {
    const token = getStoredToken();
    const invoiceId = invoiceIdFromClaim(task.description);
    if (!token || !invoiceId) return;
    setConfirming(task.id);
    try {
      await confirmInvoicePayment(token, invoiceId);
      notify('Cobro confirmado. La factura pasa a pagada.');
      reload();
    } catch (err) {
      notify(err instanceof ApiError ? err.message : 'No se pudo confirmar el cobro', 'error');
    } finally {
      setConfirming(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Tareas" description="Lo que hay que hacer hoy, de todas las familias." />
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {tasks === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : tasks.length === 0 ? (
        <EmptyState
          title="No hay tareas."
          description="Crea recordatorios desde la ficha de cada familia."
        />
      ) : (
        <>
          <Card className="flex flex-col gap-3">
            <h2 className="font-medium">Pendientes ({pending.length})</h2>
            {pending.length === 0 ? (
              <p className="text-sm text-muted">Nada pendiente.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {pending.map((task) => (
                  <li
                    key={task.id}
                    className="flex flex-wrap items-center justify-between gap-2 text-sm"
                  >
                    <span>
                      <input
                        type="checkbox"
                        className="mr-2"
                        checked={false}
                        onChange={() => toggle(task)}
                      />
                      {task.title}
                      {task.due_date && (
                        <span className="ml-2 text-muted">· {formatDate(task.due_date)}</span>
                      )}
                    </span>
                    <span className="flex items-center gap-2">
                      {task.title === PAYMENT_CLAIM_TITLE &&
                        invoiceIdFromClaim(task.description) && (
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={confirming === task.id}
                            onClick={() => confirmClaim(task)}
                          >
                            {confirming === task.id ? 'Confirmando...' : 'Confirmar cobro'}
                          </Button>
                        )}
                      {task.family_id && (
                        <Link
                          href={`/dashboard/families/${task.family_id}`}
                          className="text-brand hover:underline"
                        >
                          {task.family_name ?? 'Familia'}
                        </Link>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {done.length > 0 && (
            <Card className="flex flex-col gap-3">
              <h2 className="font-medium">Hechas</h2>
              <ul className="flex flex-col gap-1 text-sm text-muted">
                {done.map((task) => (
                  <li key={task.id}>
                    <Button variant="ghost" size="sm" onClick={() => toggle(task)}>
                      Reabrir
                    </Button>{' '}
                    <span className="line-through">{task.title}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
