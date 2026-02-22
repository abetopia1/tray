'use client';

import { createContext, useContext, type ReactNode } from 'react';
import type { AdminRole } from '@/types/database';
import { canPerformAction } from '@/lib/permissions';

interface AdminContextValue {
  userId: string;
  email: string;
  roles: AdminRole[];
  can: (action: string) => boolean;
}

const AdminContext = createContext<AdminContextValue | null>(null);

export function AdminProvider({
  children,
  userId,
  email,
  roles,
}: {
  children: ReactNode;
  userId: string;
  email: string;
  roles: AdminRole[];
}) {
  const can = (action: string) => canPerformAction(action, roles);

  return (
    <AdminContext.Provider value={{ userId, email, roles, can }}>
      {children}
    </AdminContext.Provider>
  );
}

export function useAdmin(): AdminContextValue {
  const ctx = useContext(AdminContext);
  if (!ctx) throw new Error('useAdmin must be used within AdminProvider');
  return ctx;
}
