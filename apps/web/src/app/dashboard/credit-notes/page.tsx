'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { getDocuments, type StoredDocument } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { formatDate } from '@/lib/format';
import { Card } from '@/components/ui/card';
import { DownloadDocumentButton } from '@/components/ui/download-document';
import { EmptyState } from '@/components/ui/empty-state';
import { PageHeader } from '@/components/ui/page-header';

export default function CreditNotesPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [documents, setDocuments] = useState<StoredDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;
    getDocuments(token, 'credit_note')
      .then(setDocuments)
      .catch(() => setError('No se pudieron cargar las notas de crédito'));
  }, []);

  if (loading) return null;
  if (user && user.role === 'parent') {
    router.replace('/dashboard');
    return null;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Notas de crédito"
        description="Abonos detectados en el buzón. El padre no ve esta cola."
      />
      {error && <p className="text-sm text-rose-700">{error}</p>}
      {documents === null ? (
        <p className="text-sm text-muted">Cargando...</p>
      ) : documents.length === 0 ? (
        <EmptyState
          title="No hay notas de crédito."
          description="Cuando un correo traiga un abono, aparecerá aquí para revisar el PDF."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {documents.map((document) => (
            <li key={document.id}>
              <Card className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-medium">{document.original_filename ?? 'Documento'}</p>
                  <p className="text-sm text-muted">
                    {formatDate(document.created_at.slice(0, 10))}
                  </p>
                </div>
                <DownloadDocumentButton documentId={document.id} />
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
