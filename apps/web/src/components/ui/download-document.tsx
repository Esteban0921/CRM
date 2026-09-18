'use client';

import { useState } from 'react';
import { downloadDocument, ApiError } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { Button } from './button';
import { Dialog } from './dialog';

export function DownloadDocumentButton({
  documentId,
  label = 'Descargar',
}: {
  documentId: string;
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  async function loadBlob() {
    const token = getStoredToken();
    if (!token) return null;
    return downloadDocument(token, documentId);
  }

  async function handleDownload() {
    setBusy(true);
    setError(null);
    try {
      const file = await loadBlob();
      if (!file) return;
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo descargar');
    } finally {
      setBusy(false);
    }
  }

  async function handlePreview() {
    setBusy(true);
    setError(null);
    try {
      const file = await loadBlob();
      if (!file) return;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrl(URL.createObjectURL(file.blob));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo abrir el documento');
    } finally {
      setBusy(false);
    }
  }

  function closePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
  }

  return (
    <span className="flex flex-col gap-1">
      <span className="flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={handlePreview} disabled={busy}>
          {busy ? 'Abriendo...' : 'Ver PDF'}
        </Button>
        <Button variant="ghost" size="sm" onClick={handleDownload} disabled={busy}>
          {label}
        </Button>
      </span>
      {error && <span className="text-xs text-rose-700">{error}</span>}
      <Dialog open={Boolean(previewUrl)} title="Factura" onClose={closePreview}>
        {previewUrl && (
          <iframe
            title="Vista de la factura"
            src={previewUrl}
            className="h-[70vh] w-full rounded-lg border border-line"
          />
        )}
      </Dialog>
    </span>
  );
}
