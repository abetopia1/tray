import { createServerSupabaseClient } from '@/lib/supabase/server';
import { redirect } from 'next/navigation';
import type { AdminRole } from '@/types/database';
import { getVisibleNavItems } from '@/lib/permissions';
import { AdminProvider } from './context';
import AdminShell from './components/AdminShell';

const NAV_META: Record<string, { labelEn: string; labelAr: string }> = {
  '/admin':              { labelEn: 'Hub',            labelAr: 'المركز' },
  '/admin/users':        { labelEn: 'Users',          labelAr: 'المستخدمون' },
  '/admin/transactions': { labelEn: 'Transactions',   labelAr: 'المعاملات' },
  '/admin/kyc':          { labelEn: 'KYC',            labelAr: 'التحقق من الهوية' },
  '/admin/settlement':   { labelEn: 'Settlement',     labelAr: 'التسوية' },
  '/admin/support':      { labelEn: 'Support',        labelAr: 'الدعم' },
  '/admin/jobs':         { labelEn: 'Jobs',           labelAr: 'المهام' },
};

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect('/login?redirect=/admin');
  }

  const { data: roles } = await supabase
    .from('user_roles')
    .select('role')
    .eq('user_id', user.id)
    .in('role', ['admin', 'compliance', 'finance', 'support']);

  if (!roles || roles.length === 0) {
    redirect('/unauthorized');
  }

  const userRoles = roles.map((r: { role: AdminRole }) => r.role);
  const visiblePaths = getVisibleNavItems(userRoles);

  const navItems = visiblePaths
    .map((path) => {
      const meta = NAV_META[path];
      if (!meta) return null;
      return { href: path, labelEn: meta.labelEn, labelAr: meta.labelAr };
    })
    .filter(Boolean) as { href: string; labelEn: string; labelAr: string }[];

  return (
    <AdminProvider userId={user.id} email={user.email ?? ''} roles={userRoles}>
      <AdminShell
        email={user.email ?? ''}
        roles={userRoles}
        navItems={navItems}
      >
        {children}
      </AdminShell>
    </AdminProvider>
  );
}
