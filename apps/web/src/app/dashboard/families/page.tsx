'use client';

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { createFamily, getFamilies, ApiError, type Family } from '@/lib/api';
import { formatAmount } from '@/lib/format';
import { getStoredToken } from '@/lib/auth-storage';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Dialog } from '@/components/ui/dialog';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { PageHeader } from '@/components/ui/page-header';
import { useToast } from '@/components/ui/toast';

export default function FamiliesPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const { notify } = useToast();
  const [families, setFamilies] = useState<Family[] | null>(null);
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState('');
  const [onlyAttention, setOnlyAttention] = useState(false);

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
      setOpen(false);
      notify('Familia creada');
      reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear la familia');
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Familias"
        description="Alumnos, contratos y facturación por familia."
        actions={<Button onClick={() => setOpen(true)}>Nueva familia</Button>}
      />

      <Dialog open={open} title="Nueva familia" onClose={() => setOpen(false)}>
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <Input
            label="Nombre"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <Input
            label="Dirección (opcional)"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
          />
          {error && <p className="text-sm text-rose-700">{error}</p>}
          <Button type="submit" disabled={submitting}>
            Añadir familia
          </Button>
        </form>
      </Dialog>

      {error && !open && <p className="text-sm text-rose-700">{error}</p>}
      {families && families.length > 0 && (
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <Input
              label="Filtrar listado"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input
              type="checkbox"
              checked={onlyAttention}
              onChange={(event) => setOnlyAttention(event.target.checked)}
            />
            Solo deuda o sin facturar
          </label>
        </div>
      )}
      {families === null ? (
        error ? null : (
          <p className="text-sm text-muted">Cargando...</p>
        )
      ) : families.length === 0 ? (
        <EmptyState
          title="Todavía no hay familias."
          description="Crea la primera para poder dar de alta alumnos y contratos."
          action={<Button onClick={() => setOpen(true)}>Nueva familia</Button>}
        />
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line bg-canvas/80 text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Nombre</th>
                <th className="px-4 py-3 font-medium">Dirección</th>
                <th className="px-4 py-3 font-medium">Cobro</th>
                <th className="px-4 py-3 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {families
                .filter((family) => {
                  const matchesName =
                    !filter.trim() ||
                    family.name.toLowerCase().includes(filter.trim().toLowerCase());
                  const needsAttention =
                    family.unbilled || Number(family.outstanding_amount ?? 0) > 0;
                  return matchesName && (!onlyAttention || needsAttention);
                })
                .map((family) => (
                  <tr key={family.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/families/${family.id}`}
                        className="font-medium text-brand hover:underline"
                      >
                        {family.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted">{family.address ?? '—'}</td>
                    <td className="px-4 py-3">
                      {family.unbilled ? (
                        <Badge tone="amber">Sin facturar</Badge>
                      ) : Number(family.overdue_amount ?? 0) > 0 ? (
                        <span className="text-rose-700 tabular">
                          {formatAmount(family.overdue_amount, family.currency)} vencida
                        </span>
                      ) : Number(family.outstanding_amount ?? 0) > 0 ? (
                        <span className="tabular">
                          {formatAmount(family.outstanding_amount, family.currency)}
                        </span>
                      ) : (
                        <span className="text-muted">Al día</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={family.status === 'active' ? 'emerald' : 'slate'}>
                        {family.status === 'active' ? 'Activa' : 'Inactiva'}
                      </Badge>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
