'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { search, type SearchHit } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { useAuth } from '@/lib/auth-context';

const COMMANDS = [
  { label: 'Inicio', href: '/dashboard' },
  { label: 'Cola de revisión', href: '/dashboard/invoices' },
  { label: 'Tareas', href: '/dashboard/tasks' },
  { label: 'Notas de crédito', href: '/dashboard/credit-notes' },
  { label: 'Familias', href: '/dashboard/families' },
  { label: 'Proveedores', href: '/dashboard/suppliers' },
  { label: 'Correos ingeridos', href: '/dashboard/emails' },
  { label: 'Buscar', href: '/dashboard/search' },
  { label: 'Inicio / huecos del mes', href: '/dashboard' },
  { label: 'Cierre del mes', href: '/dashboard' },
];

export function CommandPalette() {
  const { user } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<SearchHit[]>([]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setOpen((value) => !value);
      }
      if (event.key === 'Escape') setOpen(false);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!open || q.trim().length < 2) {
      setHits([]);
      return;
    }
    const token = getStoredToken();
    if (!token) return;
    const handle = window.setTimeout(() => {
      search(token, q.trim())
        .then((result) => setHits(result.hits))
        .catch(() => setHits([]));
    }, 200);
    return () => window.clearTimeout(handle);
  }, [q, open]);

  if (!user || user.role === 'parent' || !open) return null;

  const filteredCommands = COMMANDS.filter((command) =>
    command.label.toLowerCase().includes(q.trim().toLowerCase()),
  );

  function go(href: string) {
    setOpen(false);
    setQ('');
    router.push(href);
  }

  function hrefFor(hit: SearchHit): string {
    if (hit.type === 'supplier') return '/dashboard/suppliers';
    return hit.family_id ? `/dashboard/families/${hit.family_id}` : '/dashboard/families';
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 px-4 pt-24"
      onClick={() => setOpen(false)}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-line bg-paper shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <input
          autoFocus
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Ir a… o buscar familias"
          aria-label="Paleta de comandos"
          className="w-full border-b border-line bg-transparent px-4 py-3 text-sm outline-none"
        />
        <ul className="max-h-80 overflow-y-auto p-2 text-sm">
          {filteredCommands.map((command) => (
            <li key={command.href}>
              <button
                type="button"
                onClick={() => go(command.href)}
                className="w-full rounded-lg px-3 py-2 text-left hover:bg-canvas"
              >
                {command.label}
              </button>
            </li>
          ))}
          {hits.map((hit) => (
            <li key={`${hit.type}-${hit.id}`}>
              <button
                type="button"
                onClick={() => go(hrefFor(hit))}
                className="w-full rounded-lg px-3 py-2 text-left hover:bg-canvas"
              >
                <span className="text-xs uppercase text-muted">{hit.type}</span>
                <span className="ml-2">{hit.title}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-line px-4 py-2 text-xs text-muted">
          Esc cierra · Ctrl+K abre
        </p>
      </div>
    </div>
  );
}
