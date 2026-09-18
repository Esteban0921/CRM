'use client';

import { use, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  anonymizeFamily,
  createContract,
  createNote,
  createStudent,
  createTask,
  createUser,
  deleteNote,
  exportFamily,
  getContracts,
  confirmInvoicePayment,
  getFamily,
  getFamilyActivity,
  getFamilyBilling,
  getFamilyInvoices,
  getNotes,
  getStudents,
  getTasks,
  getUsers,
  updateContract,
  updateFamily,
  updateStudent,
  updateTask,
  ApiError,
  type Contract,
  type ActivityEvent,
  type Family,
  type FamilyBilling,
  type FamilyInvoice,
  type MeResponse,
  type Note,
  type Student,
  type Task,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import {
  FAMILY_INVOICE_LABELS,
  FAMILY_INVOICE_TONES,
  formatAmount,
  formatDate,
} from '@/lib/format';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Dialog } from '@/components/ui/dialog';
import { Input, Select } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

export default function FamilyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { notify } = useToast();
  const [family, setFamily] = useState<Family | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [parents, setParents] = useState<MeResponse[]>([]);
  const [billing, setBilling] = useState<FamilyBilling | null>(null);
  const [invoices, setInvoices] = useState<FamilyInvoice[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmAnon, setConfirmAnon] = useState(false);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getFamily(token, id)
      .then(setFamily)
      .catch(() => setError('No se pudo cargar la familia'));
    getStudents(token, id)
      .then(setStudents)
      .catch(() => {});
    getContracts(token)
      .then((rows) => setContracts(rows))
      .catch(() => {});
    getNotes(token, 'family', id)
      .then(setNotes)
      .catch(() => {});
    getTasks(token, id)
      .then(setTasks)
      .catch(() => {});
    getUsers(token, id)
      .then((rows) => setParents(rows.filter((member) => member.role === 'parent')))
      .catch(() => {});
    getFamilyBilling(token, id)
      .then(setBilling)
      .catch(() => {});
    getFamilyInvoices(token, undefined, id)
      .then(setInvoices)
      .catch(() => setInvoices([]));
    getFamilyActivity(token, id)
      .then(setActivity)
      .catch(() => {});
  }

  useEffect(reload, [id]);

  async function handleStatusToggle() {
    const token = getStoredToken();
    if (!token || !family) return;
    const nextStatus = family.status === 'active' ? 'inactive' : 'active';
    await updateFamily(token, id, { status: nextStatus });
    reload();
  }

  async function handleExport() {
    const token = getStoredToken();
    if (!token) return;
    const data = await exportFamily(token, id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `familia-${id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    notify('Exportación descargada');
  }

  async function handleAnonymize() {
    const token = getStoredToken();
    if (!token) return;
    await anonymizeFamily(token, id);
    setConfirmAnon(false);
    notify('Familia anonimizada');
    reload();
  }

  if (authLoading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  if (error) return <p className="text-sm text-rose-700">{error}</p>;
  if (!family) return <p className="text-sm text-muted">Cargando...</p>;

  const familyContracts = contracts.filter((contract) =>
    students.some((student) => student.id === contract.student_id),
  );

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm">
        <Link href="/dashboard/families" className="text-brand hover:underline">
          Familias
        </Link>
        <span className="text-muted"> / {family.name}</span>
      </p>
      <PageHeader
        title={family.name}
        description={family.address ?? 'Sin dirección'}
        actions={
          <>
            <Badge tone={family.status === 'active' ? 'emerald' : 'slate'}>
              {family.status === 'active' ? 'Activa' : 'Inactiva'}
            </Badge>
            <Button variant="secondary" onClick={handleStatusToggle}>
              Marcar como {family.status === 'active' ? 'inactiva' : 'activa'}
            </Button>
            <Button variant="secondary" onClick={handleExport}>
              Exportar datos (RGPD)
            </Button>
            <Button variant="danger" onClick={() => setConfirmAnon(true)}>
              Anonimizar (RGPD)
            </Button>
          </>
        }
      />

      <Dialog open={confirmAnon} title="Anonimizar familia" onClose={() => setConfirmAnon(false)}>
        <p className="text-sm text-muted">
          Esto pisa nombre, dirección, emails y datos de alumnos de forma irreversible. Los importes
          de facturación se conservan. ¿Continuar?
        </p>
        <div className="mt-4 flex gap-2">
          <Button variant="danger" onClick={handleAnonymize}>
            Anonimizar
          </Button>
          <Button variant="secondary" onClick={() => setConfirmAnon(false)}>
            Cancelar
          </Button>
        </div>
      </Dialog>

      <FamilyInvoicesSection familyId={id} invoices={invoices} onChange={reload} />
      {billing && (
        <Card>
          <h2 className="font-medium">Facturación</h2>
          <dl className="mt-3 grid gap-3 text-sm md:grid-cols-3">
            <div>
              <dt className="text-muted">Pendiente</dt>
              <dd className="mt-1 text-lg font-semibold tabular">
                {formatAmount(billing.outstanding_amount, billing.currency)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Vencido</dt>
              <dd className="mt-1 text-lg font-semibold tabular">
                {formatAmount(billing.overdue_amount, billing.currency)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Pagadas</dt>
              <dd className="mt-1 text-lg font-semibold tabular">{billing.paid_count}</dd>
            </div>
          </dl>
        </Card>
      )}

      <ParentsSection familyId={id} parents={parents} onChange={reload} />
      <StudentsSection familyId={id} students={students} onChange={reload} />
      <ContractsSection students={students} contracts={familyContracts} onChange={reload} />
      <NotesSection familyId={id} notes={notes} onChange={reload} />
      <TasksSection familyId={id} tasks={tasks} onChange={reload} />
      <ActivitySection events={activity} />
    </div>
  );
}

function FamilyInvoicesSection({
  familyId,
  invoices,
  onChange,
}: {
  familyId: string;
  invoices: FamilyInvoice[];
  onChange: () => void;
}) {
  const { notify } = useToast();
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-medium">Facturas</h2>
        <Link
          href={`/dashboard/invoices?family_id=${familyId}`}
          className="text-sm text-brand hover:underline"
        >
          Ver en la cola
        </Link>
      </div>
      {invoices.length === 0 ? (
        <p className="text-sm text-muted">No hay facturas de esta familia.</p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {invoices.map((invoice) => (
            <li
              key={invoice.id}
              className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-2 last:border-0 last:pb-0"
            >
              <div>
                <p className="tabular font-medium">
                  {formatAmount(invoice.amount, invoice.currency)}
                </p>
                <p className="text-xs text-muted">{formatDate(invoice.issue_date)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={FAMILY_INVOICE_TONES[invoice.status] ?? 'slate'}>
                  {FAMILY_INVOICE_LABELS[invoice.status] ?? invoice.status}
                </Badge>
                <DownloadDocumentButton documentId={invoice.document_id} label="PDF" />
                {(invoice.status === 'sent' || invoice.status === 'overdue') && (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={confirming === invoice.id}
                    onClick={async () => {
                      const token = getStoredToken();
                      if (!token) return;
                      setConfirming(invoice.id);
                      try {
                        await confirmInvoicePayment(token, invoice.id);
                        notify('Cobro confirmado.');
                        onChange();
                      } catch (err) {
                        notify(
                          err instanceof ApiError ? err.message : 'No se pudo confirmar el cobro',
                          'error',
                        );
                      } finally {
                        setConfirming(null);
                      }
                    }}
                  >
                    {confirming === invoice.id ? 'Confirmando...' : 'Confirmar cobro'}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function ActivitySection({ events }: { events: ActivityEvent[] }) {
  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium">Historial</h2>
      {events.length === 0 ? (
        <p className="text-sm text-muted">Aún no hay cambios registrados en esta ficha.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {events.map((event, index) => (
            <li key={`${event.at}-${index}`} className="border-l-2 border-line pl-3 text-sm">
              <p className="text-xs text-muted">
                {formatDate(event.at.slice(0, 10))}
                {event.actor_name ? ` · ${event.actor_name}` : ''}
              </p>
              <p className="font-medium text-ink">{event.title}</p>
              {event.detail && <p className="text-muted">{event.detail}</p>}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

function ParentsSection({
  familyId,
  parents,
  onChange,
}: {
  familyId: string;
  parents: MeResponse[];
  onChange: () => void;
}) {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await createUser(token, {
        name,
        email,
        password,
        role: 'parent',
        family_id: familyId,
      });
      setName('');
      setEmail('');
      setPassword('');
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo dar de alta al padre');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="flex flex-col gap-4">
      <h2 className="font-medium">Acceso de la familia</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {parents.length === 0 ? (
          <li className="text-muted">Todavía no hay un padre con usuario.</li>
        ) : (
          parents.map((parent) => (
            <li key={parent.id}>
              {parent.name} <span className="text-muted">· {parent.email}</span>
            </li>
          ))
        )}
      </ul>
      <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4 md:items-end">
        <Input
          label="Nombre"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label="Email"
          type="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Input
          label="Contraseña inicial"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" disabled={submitting}>
          Invitar padre
        </Button>
      </form>
      {error && <p className="text-sm text-rose-700">{error}</p>}
    </Card>
  );
}

function StudentsSection({
  familyId,
  students,
  onChange,
}: {
  familyId: string;
  students: Student[];
  onChange: () => void;
}) {
  const [name, setName] = useState('');
  const [school, setSchool] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Student | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    try {
      await createStudent(token, {
        family_id: familyId,
        name,
        school: school || undefined,
      });
      setName('');
      setSchool('');
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo añadir el alumno');
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const token = getStoredToken();
    if (!token) return;
    await updateStudent(token, editing.id, {
      name: editing.name,
      school: editing.school,
      birth_date: editing.birth_date,
      status: editing.status,
    });
    setEditing(null);
    onChange();
  }

  return (
    <Card className="flex flex-col gap-4">
      <h2 className="font-medium">Alumnos</h2>
      <ul className="flex flex-col gap-2 text-sm">
        {students.map((student) => (
          <li key={student.id} className="flex flex-wrap items-center justify-between gap-2">
            <span>
              {student.name}{' '}
              <span className="text-muted">
                {student.school ? `· ${student.school}` : ''} · {student.status}
              </span>
            </span>
            <Button variant="ghost" size="sm" onClick={() => setEditing(student)}>
              Editar
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
        <Input
          label="Nombre del alumno"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label="Colegio (opcional)"
          value={school}
          onChange={(event) => setSchool(event.target.value)}
        />
        <Button type="submit">Añadir alumno</Button>
      </form>
      {error && <p className="text-sm text-rose-700">{error}</p>}

      <Dialog open={Boolean(editing)} title="Editar alumno" onClose={() => setEditing(null)}>
        {editing && (
          <form onSubmit={handleSave} className="flex flex-col gap-3">
            <Input
              label="Nombre"
              required
              value={editing.name}
              onChange={(event) => setEditing({ ...editing, name: event.target.value })}
            />
            <Input
              label="Colegio"
              value={editing.school ?? ''}
              onChange={(event) => setEditing({ ...editing, school: event.target.value })}
            />
            <Input
              label="Fecha de nacimiento"
              type="date"
              value={editing.birth_date ?? ''}
              onChange={(event) =>
                setEditing({ ...editing, birth_date: event.target.value || null })
              }
            />
            <Select
              label="Estado"
              value={editing.status}
              onChange={(event) =>
                setEditing({ ...editing, status: event.target.value as Student['status'] })
              }
            >
              <option value="active">Activo</option>
              <option value="inactive">Inactivo</option>
            </Select>
            <Button type="submit">Guardar</Button>
          </form>
        )}
      </Dialog>
    </Card>
  );
}

function ContractsSection({
  students,
  contracts,
  onChange,
}: {
  students: Student[];
  contracts: Contract[];
  onChange: () => void;
}) {
  const [studentId, setStudentId] = useState(students[0]?.id ?? '');
  const [serviceType, setServiceType] = useState('Ruta mañana');
  const [fee, setFee] = useState('45.00');
  const [startDate, setStartDate] = useState('2026-09-01');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!studentId && students[0]) setStudentId(students[0].id);
  }, [students, studentId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token || !studentId) return;
    try {
      await createContract(token, {
        student_id: studentId,
        service_type: serviceType,
        monthly_fee: fee,
        start_date: startDate,
      });
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear el contrato');
    }
  }

  async function handleStatus(contract: Contract, status: Contract['status']) {
    const token = getStoredToken();
    if (!token) return;
    await updateContract(token, contract.id, { status });
    onChange();
  }

  const studentName = (id: string) =>
    students.find((student) => student.id === id)?.name ?? 'Alumno';

  return (
    <Card className="flex flex-col gap-4">
      <h2 className="font-medium">Contratos</h2>
      {contracts.length === 0 ? (
        <p className="text-sm text-muted">Todavía no hay contratos de servicio.</p>
      ) : (
        <ul className="flex flex-col gap-2 text-sm">
          {contracts.map((contract) => (
            <li key={contract.id} className="flex flex-wrap items-center justify-between gap-2">
              <span>
                {studentName(contract.student_id)} · {contract.service_type} ·{' '}
                <span className="tabular">{formatAmount(contract.monthly_fee)}</span> · desde{' '}
                {formatDate(contract.start_date)}
              </span>
              <span className="flex items-center gap-2">
                <Badge tone={contract.status === 'active' ? 'emerald' : 'slate'}>
                  {contract.status}
                </Badge>
                {contract.status === 'active' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStatus(contract, 'paused')}
                  >
                    Pausar
                  </Button>
                )}
                {contract.status === 'paused' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStatus(contract, 'active')}
                  >
                    Reactivar
                  </Button>
                )}
                {contract.status !== 'cancelled' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStatus(contract, 'cancelled')}
                  >
                    Cancelar
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {students.length === 0 ? (
        <p className="text-sm text-muted">Añade un alumno antes de crear un contrato.</p>
      ) : (
        <form onSubmit={handleSubmit} className="grid gap-3 md:grid-cols-4 md:items-end">
          <Select
            label="Alumno"
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
          >
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.name}
              </option>
            ))}
          </Select>
          <Input
            label="Servicio"
            required
            value={serviceType}
            onChange={(event) => setServiceType(event.target.value)}
          />
          <Input
            label="Cuota mensual"
            required
            value={fee}
            onChange={(event) => setFee(event.target.value)}
          />
          <Input
            label="Inicio"
            type="date"
            required
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
          <Button type="submit">Añadir contrato</Button>
        </form>
      )}
      {error && <p className="text-sm text-rose-700">{error}</p>}
    </Card>
  );
}

function NotesSection({
  familyId,
  notes,
  onChange,
}: {
  familyId: string;
  notes: Note[];
  onChange: () => void;
}) {
  const [body, setBody] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token || !body.trim()) return;
    await createNote(token, { entity_type: 'family', entity_id: familyId, body });
    setBody('');
    onChange();
  }

  async function handleDelete(noteId: string) {
    const token = getStoredToken();
    if (!token) return;
    await deleteNote(token, noteId);
    onChange();
  }

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium">Notas internas</h2>
      <ul className="flex flex-col gap-2 text-sm">
        {notes.map((note) => (
          <li
            key={note.id}
            className="flex justify-between gap-2 rounded-lg border border-line px-3 py-2"
          >
            <span>{note.body}</span>
            <button
              type="button"
              onClick={() => handleDelete(note.id)}
              className="text-muted hover:text-rose-700"
            >
              borrar
            </button>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Nueva nota"
          className="flex-1 rounded-lg border border-line bg-paper px-3 py-2 text-sm"
        />
        <Button type="submit">Añadir nota</Button>
      </form>
    </Card>
  );
}

function TasksSection({
  familyId,
  tasks,
  onChange,
}: {
  familyId: string;
  tasks: Task[];
  onChange: () => void;
}) {
  const [title, setTitle] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token || !title.trim()) return;
    await createTask(token, { family_id: familyId, title });
    setTitle('');
    onChange();
  }

  async function toggleDone(task: Task) {
    const token = getStoredToken();
    if (!token) return;
    await updateTask(token, task.id, { status: task.status === 'done' ? 'pending' : 'done' });
    onChange();
  }

  return (
    <Card className="flex flex-col gap-3">
      <h2 className="font-medium">Tareas</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {tasks.map((task) => (
          <li key={task.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={task.status === 'done'}
              onChange={() => toggleDone(task)}
            />
            <span className={task.status === 'done' ? 'text-muted line-through' : ''}>
              {task.title}
            </span>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Nueva tarea"
          className="flex-1 rounded-lg border border-line bg-paper px-3 py-2 text-sm"
        />
        <Button type="submit">Añadir tarea</Button>
      </form>
    </Card>
  );
}
