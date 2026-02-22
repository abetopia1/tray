'use client';

import { useEffect, useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import type { AdminKpis } from '@/types/database';

const KPI_KEYS = ['total_users', 'total_merchants', 'today_volume', 'today_fees', 'failed_tx_count', 'new_users_today'] as const;
const KPI_COLORS: Record<string, string> = {
  total_users: '#3b82f6',
  total_merchants: '#8b5cf6',
  today_volume: '#10b981',
  today_fees: '#f59e0b',
  failed_tx_count: '#ef4444',
  new_users_today: '#06b6d4',
};

function formatValue(value: number, key: string, locale: string): string {
  const loc = locale === 'ar' ? 'ar-SA' : 'en-US';
  if (key === 'today_volume' || key === 'today_fees') {
    return new Intl.NumberFormat(loc, { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(value);
  }
  return new Intl.NumberFormat(loc).format(value);
}

export default function KpiCards({ refreshKey }: { refreshKey?: number }) {
  const { locale } = useI18n();
  const [kpis, setKpis] = useState<AdminKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const labels: Record<string, string> = locale === 'ar' ? {
    total_users: 'إجمالي المستخدمين',
    total_merchants: 'إجمالي التجار',
    today_volume: 'حجم المدفوعات اليوم',
    today_fees: 'الرسوم المحصلة اليوم',
    failed_tx_count: 'معاملات فاشلة اليوم',
    new_users_today: 'مستخدمون جدد اليوم',
  } : {
    total_users: 'Total Users',
    total_merchants: 'Total Merchants',
    today_volume: "Today's Volume",
    today_fees: "Today's Fees",
    failed_tx_count: 'Failed Tx Today',
    new_users_today: 'New Users Today',
  };

  const fetchKpis = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data, error: fnError } = await supabase.functions.invoke('admin-kpis');
      if (fnError) throw fnError;
      setKpis(data as AdminKpis);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load KPIs');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchKpis(); }, [fetchKpis, refreshKey]);

  if (error) {
    return (
      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '1rem', color: '#dc2626' }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
      {KPI_KEYS.map((key) => {
        const value = kpis?.[key] ?? 0;
        return (
          <div key={key} style={{
            background: '#fff',
            borderRadius: '8px',
            padding: '1.25rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            borderTop: `3px solid ${KPI_COLORS[key]}`,
          }}>
            <p style={{
              margin: '0 0 0.5rem',
              fontSize: '0.75rem',
              color: '#6b7280',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600,
            }}>
              {labels[key]}
            </p>
            <p style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>
              {loading ? (
                <span style={{ display: 'inline-block', width: '60px', height: '24px', background: '#e5e7eb', borderRadius: '4px' }} />
              ) : (
                formatValue(value, key, locale)
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
