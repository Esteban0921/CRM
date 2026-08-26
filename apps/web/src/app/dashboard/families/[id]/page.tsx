'use client';

import { use, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import {
  anonymizeFamily,
  createNote,
  createStudent,
  createTask,
  deleteNote,
  exportFamily,
  getFamily,
  getNotes,
  getStudents,
  getTasks,
  updateFamily,
  updateTask,
  ApiError,
  type Family,
  type Note,
  type Student,
  type Task,
} from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';

export default function FamilyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [family, setFamily] = useState<Family | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getFamily(token, id)
      .then(setFamily)
      .catch(() => setError('No se pudo cargar la familia'));
    getStudents(token, id)
      .then(setStudents)
      .catch(() => {});
    getNotes(token, 'family', id)
      .then(setNotes)
      .catch(() => {});
    getTasks(token, id)
      .then(setTasks)
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
    console.log('Exportación RGPD', data);
    alert('Datos exportados a la consola del navegador (JSON).');
  }

  async function handleAnonymize() {
    const token = getStoredToken();
    if (!token) return;
    if (
      !confirm(
        'Esto anonimiza los datos personales de la familia de forma irreversible. ¿Continuar?',
      )
    ) {
      return;
    }
    await anonymizeFamily(token, id);
    reload();
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!family) return <p className="text-sm text-neutral-500">Cargando...</p>;

  return (
    <div className="flex max-w-2xl flex-col gap-8">
      <div>
        <h1 className="text-xl font-semibold">{family.name}</h1>
        <p className="text-sm text-neutral-500">{family.address ?? 'Sin dirección'}</p>
        <div className="mt-2 flex gap-2">
          <button onClick={handleStatusToggle} className="text-sm underline">
            Marcar como {family.status === 'active' ? 'inactiva' : 'activa'}
          </button>
          <button onClick={handleExport} className="text-sm underline">
            Exportar datos (RGPD)
          </button>
          <button onClick={handleAnonymize} className="text-sm text-red-600 underline">
            Anonimizar (RGPD)
          </button>
        </div>
      </div>

      <StudentsSection familyId={id} students={students} onChange={reload} />
      <NotesSection familyId={id} notes={notes} onChange={reload} />
      <TasksSection familyId={id} tasks={tasks} onChange={reload} />
    </div>
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
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    try {
      await createStudent(token, { family_id: familyId, name });
      setName('');
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo añadir el alumno');
    }
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="font-medium">Alumnos</h2>
      <ul className="text-sm">
        {students.map((student) => (
          <li key={student.id}>
            {student.name} <span className="text-neutral-500">({student.status})</span>
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Nombre del alumno"
          className="rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <button type="submit" className="rounded bg-neutral-900 px-3 py-1 text-sm text-white">
          Añadir alumno
        </button>
      </form>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </section>
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
    <section className="flex flex-col gap-2">
      <h2 className="font-medium">Notas internas</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {notes.map((note) => (
          <li
            key={note.id}
            className="flex justify-between gap-2 rounded border border-neutral-200 p-2"
          >
            <span>{note.body}</span>
            <button
              onClick={() => handleDelete(note.id)}
              className="text-neutral-400 hover:text-red-600"
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
          className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <button type="submit" className="rounded bg-neutral-900 px-3 py-1 text-sm text-white">
          Añadir nota
        </button>
      </form>
    </section>
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
    <section className="flex flex-col gap-2">
      <h2 className="font-medium">Tareas</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {tasks.map((task) => (
          <li key={task.id} className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={task.status === 'done'}
              onChange={() => toggleDone(task)}
            />
            <span className={task.status === 'done' ? 'line-through text-neutral-400' : ''}>
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
          className="flex-1 rounded border border-neutral-300 px-2 py-1 text-sm"
        />
        <button type="submit" className="rounded bg-neutral-900 px-3 py-1 text-sm text-white">
          Añadir tarea
        </button>
      </form>
    </section>
  );
}
