'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { getMe, type MeResponse } from './api';
import { clearStoredToken, getStoredToken } from './auth-storage';

interface AuthContextValue {
  user: MeResponse | null;
  loading: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
    router.push('/login');
  }, [router]);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      router.replace('/login');
      setLoading(false);
      return;
    }

    getMe(token)
      .then(setUser)
      .catch(() => {
        clearStoredToken();
        router.replace('/login');
      })
      .finally(() => setLoading(false));
  }, [router]);

  return <AuthContext.Provider value={{ user, loading, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
}
