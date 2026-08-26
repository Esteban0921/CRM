'use client';

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { createFamily, getFamilies, ApiError, type Family } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';

export default function FamiliesPage() {
  const [families, setFamilies] = useState<Family[] | null>(null);
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function reload() {
    const token = getStoredToken();
    if (!token) return;
    getFamilies(token)
      .then(setFamilies)
      .catch(() => setError('No se pudieron cargar las familias'));
  }

  useEffect(reload, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getStoredToken();
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await createFamily(token, { name, address: address || undefined });
      setName('');
      setAddress('');
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear la familia');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Familias</h1>

      <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-sm">
          <span>Nombre</span>
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="rounded border border-neutral-300 px-2 py-1"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span>Dirección (opcional)</span>
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            className="rounded border border-neutral-300 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          disabled={submitting}
          className="rounded bg-neutral-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          Añadir familia
        </button>
      </form>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {families === null ? (
        <p className="text-sm text-neutral-500">Cargando...</p>
      ) : families.length === 0 ? (
        <p className="text-sm text-neutral-500">Todavía no hay familias.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {families.map((family) => (
            <li key={family.id}>
              <Link href={`/dashboard/families/${family.id}`} className="text-sm underline">
                {family.name}
              </Link>
              <span className="ml-2 text-xs text-neutral-500">{family.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
