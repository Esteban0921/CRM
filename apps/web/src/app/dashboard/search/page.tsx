'use client';

import { Suspense, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { search, type SearchHit } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/ui/page-header';

const TYPE_LABELS: Record<SearchHit['type'], string> = {
  family: 'Familia',
  student: 'Alumno',
  family_invoice: 'Factura',
  supplier: 'Proveedor',
};

function hrefFor(hit: SearchHit): string {
  if (hit.type === 'family' || hit.type === 'student' || hit.type === 'family_invoice') {
    return hit.family_id ? `/dashboard/families/${hit.family_id}` : '/dashboard/families';
  }
  return '/dashboard/suppliers';
}

function SearchPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const initial = params.get('q') ?? '';
  const [q, setQ] = useState(initial);
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setQ(initial);
    const token = getStoredToken();
    if (!token || initial.trim().length < 2) {
      setHits([]);
      return;
    }
    search(token, initial.trim())
      .then((result) => setHits(result.hits))
      .catch(() => setError('No se pudo buscar'));
  }, [initial]);

  if (loading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    router.push(`/dashboard/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Buscar" description="Familias, alumnos, facturas y proveedores." />
      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-2">
        <Input
          label="Consulta"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          minLength={2}
          required
        />
        <Button type="submit">Buscar</Button>
      </form>
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {hits === null ? (
        <p className="text-sm text-muted">Escribe al menos 2 caracteres.</p>
      ) : hits.length === 0 ? (
        <EmptyState
          title="Sin resultados."
          description="Prueba con el nombre de una familia o un alumno."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {hits.map((hit) => (
            <li key={`${hit.type}-${hit.id}`}>
              <Link
                href={hrefFor(hit)}
                className="block rounded-lg border border-line bg-paper px-4 py-3 hover:border-brand/40"
              >
                <p className="text-xs uppercase tracking-wide text-muted">
                  {TYPE_LABELS[hit.type]}
                </p>
                <p className="mt-1 font-medium text-ink">{hit.title}</p>
                {hit.subtitle && <p className="text-sm text-muted">{hit.subtitle}</p>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SearchRoute() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Cargando búsqueda...</p>}>
      <SearchPage />
    </Suspense>
  );
}
