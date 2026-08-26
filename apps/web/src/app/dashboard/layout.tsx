'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { AuthProvider, useAuth } from '@/lib/auth-context';

function DashboardShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return <p className="p-6">Cargando...</p>;
  }

  if (!user) {
    return null;
  }

  const isStaff = user.role === 'staff' || user.role === 'admin';

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-neutral-200 p-4">
        <p className="mb-6 font-semibold">CRM Transporte</p>
        <nav className="flex flex-col gap-2 text-sm">
          {isStaff ? (
            <>
              <Link href="/dashboard/invoices">Cola de revisión</Link>
              <Link href="/dashboard/families">Familias</Link>
              <span>Facturas de proveedor</span>
            </>
          ) : (
            <Link href="/dashboard">Mis facturas</Link>
          )}
        </nav>
        <button onClick={logout} className="mt-8 text-sm text-neutral-500 underline">
          Cerrar sesión
        </button>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <DashboardShell>{children}</DashboardShell>
    </AuthProvider>
  );
}
