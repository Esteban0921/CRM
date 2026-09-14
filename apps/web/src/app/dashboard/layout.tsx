'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import { AuthProvider, useAuth } from '@/lib/auth-context';
import { ToastProvider } from '@/components/ui/toast';
import { Sidebar } from '@/components/shell/sidebar';
import { Button } from '@/components/ui/button';

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
        <header className="flex items-center justify-between border-b border-line bg-paper px-4 py-3 lg:hidden">
          <p className="font-semibold text-brand">CRM Transporte</p>
          <Button variant="secondary" size="sm" onClick={() => setMenuOpen(true)}>
            Menú
          </Button>
        </header>
        <main className="flex-1 p-6 lg:p-8">{children}</main>
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
