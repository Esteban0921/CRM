'use client';

import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { login, ApiError } from '@/lib/api';
import { setStoredToken } from '@/lib/auth-storage';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setExpired(new URLSearchParams(window.location.search).get('expired') === '1');
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { access_token: accessToken } = await login(email, password);
      setStoredToken(accessToken);
      router.push('/dashboard');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo iniciar sesión');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <Link href="/" className="mb-8 text-sm font-semibold tracking-tight text-brand">
        CRM Transporte
      </Link>
      <Card className="w-full max-w-sm">
        <h1 className="text-xl font-semibold text-ink">Iniciar sesión</h1>
        <p className="mt-1 text-sm text-muted">Acceso interno para familias y equipo.</p>
        {expired && (
          <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
            Sesión caducada. Vuelve a entrar.
          </p>
        )}
        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <Input
            label="Email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label="Contraseña"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error && (
            <p role="alert" className="text-sm text-rose-700">
              {error}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting ? 'Entrando...' : 'Entrar'}
          </Button>
        </form>
      </Card>
    </main>
  );
}
