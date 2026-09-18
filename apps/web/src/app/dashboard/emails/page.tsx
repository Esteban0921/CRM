'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { getEmails, type IngestedEmail } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatDate } from '@/lib/format';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';

const STATUS_LABEL: Record<IngestedEmail['processing_status'], string> = {
  pending: 'Pendiente',
  processing: 'Procesando',
  processed: 'Procesado',
  failed: 'Fallido',
  ignored: 'Ignorado',
};

const STATUS_TONE: Record<
  IngestedEmail['processing_status'],
  'amber' | 'blue' | 'emerald' | 'rose' | 'slate'
> = {
  pending: 'slate',
  processing: 'blue',
  processed: 'emerald',
  failed: 'rose',
  ignored: 'slate',
};

export default function EmailsPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [emails, setEmails] = useState<IngestedEmail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    getEmails(token)
      .then(setEmails)
      .catch(() => setError('No se pudieron cargar los correos'));
  }, []);

  if (loading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Correos ingeridos"
        description="Lo que ya ha pasado por el pipeline. Gmail real sigue en TASK-0032."
      />
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {emails === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : emails.length === 0 ? (
        <EmptyState
          title="Todavía no hay correos."
          description="Pulsa «Procesar correos de prueba» en el inicio para generar los primeros."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {emails.map((email) => (
            <li key={email.id}>
              <Card className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{email.subject ?? '(sin asunto)'}</p>
                  <p className="text-sm text-muted">
                    {email.from_address ?? 'remitente desconocido'}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {formatDate(email.created_at.slice(0, 10))} · {email.document_count} adjunto(s)
                  </p>
                  {email.error_message && (
                    <p className="mt-1 text-xs text-rose-700">{email.error_message}</p>
                  )}
                </div>
                <Badge tone={STATUS_TONE[email.processing_status]}>
                  {STATUS_LABEL[email.processing_status]}
                </Badge>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
