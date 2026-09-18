'use client';

import { useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/lib/auth-context';
import { ToastProvider } from '@/components/ui/toast';
import { Sidebar } from '@/components/shell/sidebar';
import { CommandPalette } from '@/components/shell/command-palette';
import { NotificationBell } from '@/components/shell/notification-bell';
import { Button } from '@/components/ui/button';

function StaffSearch() {
  const { user } = useAuth();
  const router = useRouter();
  const [q, setQ] = useState('');
  if (!user || user.role === 'parent') return null;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (q.trim().length < 2) return;
    router.push(`/dashboard/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-w-0 flex-1 items-center gap-2">
      <input
        value={q}
        onChange={(event) => setQ(event.target.value)}
        placeholder="Buscar familias, alumnos, facturas..."
        aria-label="Buscar"
        className="w-full max-w-md rounded-lg border border-line bg-canvas px-3 py-2 text-sm"
      />
      <Button type="submit" variant="secondary" size="sm">
        Buscar
      </Button>
    </form>
  );
}

function DashboardShell({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  if (loading) {
    return <p className="p-8 text-sm text-muted">Cargando...</p>;
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen lg:flex">
      <div className="hidden lg:block">
        <div className="sticky top-0 h-screen">
          <Sidebar />
        </div>
      </div>
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-ink/40"
            aria-label="Cerrar menú"
            onClick={() => setMenuOpen(false)}
          />
          <div className="relative h-full w-60">
            <Sidebar onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-3 border-b border-line bg-paper px-4 py-3 lg:hidden">
          <p className="font-semibold text-brand">CRM Transporte</p>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <Button variant="secondary" size="sm" onClick={() => setMenuOpen(true)}>
              Menú
            </Button>
          </div>
        </header>
        {user.role !== 'parent' ? (
          <>
            <div className="hidden items-center gap-3 border-b border-line bg-paper px-8 py-3 lg:flex">
              <StaffSearch />
              <NotificationBell />
            </div>
            <div className="border-b border-line bg-paper px-4 py-3 lg:hidden">
              <StaffSearch />
            </div>
          </>
        ) : (
          <div className="hidden justify-end border-b border-line bg-paper px-8 py-3 lg:flex">
            <NotificationBell />
          </div>
        )}
        <main className="flex-1 p-6 lg:p-8">{children}</main>
        <CommandPalette />
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ToastProvider>
        <DashboardShell>{children}</DashboardShell>
      </ToastProvider>
    </AuthProvider>
  );
}
