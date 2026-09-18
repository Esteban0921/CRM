'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getMyNotifications, getNotificationInbox, type InboxItem } from '@/lib/api';
import { getStoredToken } from '@/lib/auth-storage';
import { useAuth } from '@/lib/auth-context';

export function NotificationBell() {
  const { user } = useAuth();
  const [items, setItems] = useState<InboxItem[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!user) return;
    const token = getStoredToken();
    if (!token) return;
    const load = user.role === 'parent' ? getMyNotifications : getNotificationInbox;
    load(token)
      .then(setItems)
      .catch(() => setItems([]));
  }, [user]);

  if (!user) return null;
  const total = items.reduce((sum, item) => sum + item.count, 0);

  return (
    <div className="relative">
      <button
        type="button"
        className="relative rounded-lg px-3 py-2 text-sm text-ink hover:bg-canvas"
        onClick={() => setOpen((value) => !value)}
        aria-label="Avisos"
      >
        Avisos
        {total > 0 && (
          <span className="ml-2 rounded-full bg-rose-600 px-2 py-0.5 text-xs text-white">
            {total}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-72 rounded-xl border border-line bg-paper p-2 shadow-lg">
          {items.length === 0 ? (
            <p className="px-2 py-3 text-sm text-muted">Nada pendiente.</p>
          ) : (
            <ul className="flex flex-col">
              {items.map((item) => (
                <li key={item.kind}>
                  <Link
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className="flex justify-between rounded-lg px-3 py-2 text-sm hover:bg-canvas"
                  >
                    <span>{item.title}</span>
                    <span className="tabular text-muted">{item.count}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
