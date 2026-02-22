import { createServerSupabaseClient } from '@/lib/supabase/server';
import { redirect } from 'next/navigation';
import type { AdminRole } from '@/types/database';

const NAV_LINKS = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/kyc', label: 'KYC Reviews' },
  { href: '/admin/merchants', label: 'Merchants' },
  { href: '/admin/settlement', label: 'Settlements' },
  { href: '/admin/reconciliation', label: 'Reconciliation' },
  { href: '/admin/support', label: 'Support Tickets' },
];

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

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: '240px',
        background: '#111827',
        color: '#fff',
        padding: '1.5rem 0',
        flexShrink: 0,
      }}>
        <div style={{ padding: '0 1.5rem', marginBottom: '2rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700 }}>
            Tray Admin
          </h2>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: '#9ca3af' }}>
            {user.email}
          </p>
          <div style={{ marginTop: '0.25rem' }}>
            {userRoles.map((role) => (
              <span
                key={role}
                style={{
                  display: 'inline-block',
                  fontSize: '0.625rem',
                  background: '#374151',
                  padding: '0.125rem 0.5rem',
                  borderRadius: '9999px',
                  marginRight: '0.25rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {role}
              </span>
            ))}
          </div>
        </div>
        <nav>
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              style={{
                display: 'block',
                padding: '0.625rem 1.5rem',
                color: '#d1d5db',
                textDecoration: 'none',
                fontSize: '0.875rem',
                borderLeft: '3px solid transparent',
              }}
            >
              {link.label}
            </a>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main style={{
        flex: 1,
        background: '#f9fafb',
        padding: '2rem',
        overflow: 'auto',
      }}>
        {children}
      </main>
    </div>
  );
}
