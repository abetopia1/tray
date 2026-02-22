'use client';

import { useState, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { I18nProvider, useI18n } from '@/lib/i18n/context';
import type { AdminRole } from '@/types/database';

interface NavItem {
  href: string;
  labelEn: string;
  labelAr: string;
}

function ShellInner({
  email,
  roles,
  navItems,
  children,
}: {
  email: string;
  roles: AdminRole[];
  navItems: NavItem[];
  children: ReactNode;
}) {
  const { locale, dir, t, setLocale } = useI18n();
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const isRtl = dir === 'rtl';
  const borderSide = isRtl ? 'borderRight' : 'borderLeft';

  return (
    <div dir={dir} style={{ display: 'flex', minHeight: '100vh', direction: dir }}>
      {/* Mobile nav toggle */}
      <button
        onClick={() => setMobileNavOpen(!mobileNavOpen)}
        style={{
          position: 'fixed',
          top: '0.75rem',
          [isRtl ? 'right' : 'left']: '0.75rem',
          zIndex: 50,
          background: '#111827',
          color: '#fff',
          border: 'none',
          borderRadius: '6px',
          padding: '0.5rem 0.75rem',
          fontSize: '1.25rem',
          cursor: 'pointer',
          display: 'none',
        }}
        className="mobile-nav-toggle"
      >
        {mobileNavOpen ? '\u2715' : '\u2630'}
      </button>

      {/* Sidebar */}
      <aside
        style={{
          width: '240px',
          background: '#111827',
          color: '#fff',
          padding: '1.5rem 0',
          flexShrink: 0,
          position: 'relative',
          zIndex: 40,
          transition: 'transform 0.2s',
        }}
        className={mobileNavOpen ? 'sidebar-open' : ''}
      >
        <div style={{ padding: '0 1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 700 }}>
              {t.admin.title}
            </h2>
            <button
              onClick={() => setLocale(locale === 'ar' ? 'en' : 'ar')}
              style={{
                background: '#374151',
                color: '#d1d5db',
                border: 'none',
                borderRadius: '4px',
                padding: '0.125rem 0.5rem',
                fontSize: '0.7rem',
                cursor: 'pointer',
              }}
            >
              {locale === 'ar' ? 'EN' : 'AR'}
            </button>
          </div>
          <p style={{ margin: '0.25rem 0 0', fontSize: '0.75rem', color: '#9ca3af' }}>
            {email}
          </p>
          <div style={{ marginTop: '0.375rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
            {roles.map((role) => (
              <span
                key={role}
                style={{
                  display: 'inline-block',
                  fontSize: '0.625rem',
                  background: '#374151',
                  padding: '0.125rem 0.5rem',
                  borderRadius: '9999px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                {locale === 'ar' ? t.roles[role] : role}
              </span>
            ))}
          </div>
        </div>

        <nav>
          {navItems.map((item) => {
            const isActive = pathname === item.href || (item.href !== '/admin' && pathname.startsWith(item.href));
            return (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setMobileNavOpen(false)}
                style={{
                  display: 'block',
                  padding: '0.625rem 1.5rem',
                  color: isActive ? '#fff' : '#d1d5db',
                  textDecoration: 'none',
                  fontSize: '0.875rem',
                  [borderSide]: isActive ? '3px solid #3b82f6' : '3px solid transparent',
                  background: isActive ? 'rgba(59,130,246,0.1)' : 'transparent',
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                {locale === 'ar' ? item.labelAr : item.labelEn}
              </a>
            );
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main style={{
        flex: 1,
        background: '#f9fafb',
        padding: '2rem',
        overflow: 'auto',
        minWidth: 0,
      }}>
        {children}
      </main>

      {/* Mobile responsive styles */}
      <style>{`
        @media (max-width: 768px) {
          .mobile-nav-toggle { display: block !important; }
          aside {
            position: fixed !important;
            top: 0;
            ${isRtl ? 'right' : 'left'}: 0;
            height: 100vh;
            transform: translateX(${mobileNavOpen ? '0' : (isRtl ? '100%' : '-100%')});
          }
          main { padding: 1rem !important; padding-top: 3.5rem !important; }
        }
      `}</style>
    </div>
  );
}

export default function AdminShell({
  email,
  roles,
  navItems,
  children,
}: {
  email: string;
  roles: AdminRole[];
  navItems: NavItem[];
  children: ReactNode;
}) {
  return (
    <I18nProvider defaultLocale="ar">
      <ShellInner email={email} roles={roles} navItems={navItems}>
        {children}
      </ShellInner>
    </I18nProvider>
  );
}
