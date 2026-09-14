'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { cx } from '@/lib/cx';
import { Button } from '@/components/ui/button';
import { IconFamilies, IconHome, IconInbox, IconTruck } from './icons';

const staffLinks = [
  { href: '/dashboard', label: 'Inicio', icon: IconHome },
  { href: '/dashboard/invoices', label: 'Cola de revisión', icon: IconInbox },
  { href: '/dashboard/families', label: 'Familias', icon: IconFamilies },
  { href: '/dashboard/suppliers', label: 'Proveedores', icon: IconTruck },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  if (!user) return null;
  const isStaff = user.role === 'staff' || user.role === 'admin';
  const links = isStaff
    ? staffLinks
    : [{ href: '/dashboard', label: 'Mis facturas', icon: IconInbox }];

  return (
    <aside className="flex h-full w-60 flex-col bg-sidebar text-white">
      <div className="px-5 py-6">
        <p className="text-xs tracking-[0.2em] text-sidebar-muted uppercase">CRM</p>
        <p className="text-lg font-semibold">Transporte</p>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3">
        {links.map((link) => {
          const active =
            link.href === '/dashboard' ? pathname === '/dashboard' : pathname.startsWith(link.href);
          const Icon = link.icon;
          return (
            <Link
              key={link.href}
              href={link.href}
              onClick={onNavigate}
              className={cx(
                'flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition',
                active
                  ? 'bg-white/10 text-white'
                  : 'text-sidebar-muted hover:bg-white/5 hover:text-white',
              )}
            >
              <Icon />
              {link.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 px-4 py-4">
        <p className="truncate text-sm font-medium">{user.name}</p>
        <p className="text-xs text-sidebar-muted capitalize">
          {user.role === 'parent' ? 'familia' : user.role}
        </p>
        <Button variant="ghost" size="sm" className="mt-3 text-sidebar-muted" onClick={logout}>
          Cerrar sesión
        </Button>
      </div>
    </aside>
  );
}
