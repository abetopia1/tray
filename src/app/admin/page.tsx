'use client';

import { useState, useCallback } from 'react';
import { useI18n } from '@/lib/i18n/context';
import KpiCards from './components/KpiCards';
import ActionQueues from './components/ActionQueues';
import GlobalSearch from './components/GlobalSearch';

export default function AdminDashboard() {
  const { t, locale } = useI18n();
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setLastUpdated(new Date());
  }, []);

  const fmtTime = new Intl.DateTimeFormat(locale === 'ar' ? 'ar-SA' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(lastUpdated);

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ margin: '0 0 0.25rem', fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>
            {locale === 'ar' ? t.admin.hub : 'Hub'}
          </h1>
          <p style={{ margin: 0, color: '#6b7280', fontSize: '0.8rem' }}>
            {locale === 'ar' ? t.admin.lastUpdated : 'Last updated'}: {fmtTime}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          style={{
            padding: '0.5rem 1rem',
            background: '#111827',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.85rem',
            cursor: 'pointer',
          }}
        >
          {locale === 'ar' ? t.admin.refresh : 'Refresh'}
        </button>
      </div>

      {/* Global Search */}
      <section style={{ marginBottom: '1.5rem' }}>
        <GlobalSearch />
      </section>

      {/* KPI Cards */}
      <section style={{ marginBottom: '1.5rem' }}>
        <KpiCards refreshKey={refreshKey} />
      </section>

      {/* Action Queues */}
      <section style={{ marginBottom: '1.5rem' }}>
        <ActionQueues refreshKey={refreshKey} />
      </section>

      {/* Jump links */}
      <section>
        <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600, color: '#111827' }}>
          {locale === 'ar' ? 'الوصول السريع' : 'Quick Access'}
        </h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          {[
            { href: '/admin/users', label: locale === 'ar' ? 'المستخدمون' : 'Users' },
            { href: '/admin/transactions', label: locale === 'ar' ? 'المعاملات' : 'Transactions' },
            { href: '/admin/kyc', label: locale === 'ar' ? 'التحقق' : 'KYC' },
            { href: '/admin/settlement', label: locale === 'ar' ? 'التسوية' : 'Settlement' },
            { href: '/admin/support', label: locale === 'ar' ? 'الدعم' : 'Support' },
          ].map((link) => (
            <a
              key={link.href}
              href={link.href}
              style={{
                padding: '0.5rem 1rem',
                background: '#fff',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                color: '#111827',
                textDecoration: 'none',
                fontSize: '0.85rem',
                fontWeight: 500,
              }}
            >
              {link.label}
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
