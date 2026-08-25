'use client';

import { useAuth } from '@/lib/auth-context';

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) return null;

  const roleLabel = user.role === 'parent' ? 'Familia' : 'Equipo interno';

  return (
    <div>
      <h1 className="text-xl font-semibold">Hola, {user.name}</h1>
      <p className="text-sm text-neutral-500">{roleLabel}</p>
    </div>
  );
}
