'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { AdminKpis } from '@/types/database';

const KPI_CONFIG = [
  { key: 'total_users', label: 'Total Users', format: 'number', color: '#3b82f6' },
  { key: 'total_merchants', label: 'Total Merchants', format: 'number', color: '#8b5cf6' },
  { key: 'today_volume', label: "Today's Volume", format: 'currency', color: '#10b981' },
  { key: 'today_fees', label: "Today's Fees", format: 'currency', color: '#f59e0b' },
  { key: 'failed_tx_count', label: 'Failed Transactions', format: 'number', color: '#ef4444' },
] as const;

function formatValue(value: number, format: string): string {
  if (format === 'currency') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(value);
  }
  return new Intl.NumberFormat('en-US').format(value);
}

export default function KpiCards() {
  const [kpis, setKpis] = useState<AdminKpis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchKpis() {
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
    }

    fetchKpis();
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        {KPI_CONFIG.map((kpi) => (
          <div key={kpi.key} style={{
            background: '#fff',
            borderRadius: '8px',
            padding: '1.25rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            height: '100px',
          }}>
            <div style={{ height: '12px', width: '60%', background: '#e5e7eb', borderRadius: '4px', marginBottom: '0.75rem' }} />
            <div style={{ height: '24px', width: '40%', background: '#e5e7eb', borderRadius: '4px' }} />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '1rem', color: '#dc2626' }}>
        {error}
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
      {KPI_CONFIG.map((kpi) => {
        const value = kpis?.[kpi.key] ?? 0;
        return (
          <div key={kpi.key} style={{
            background: '#fff',
            borderRadius: '8px',
            padding: '1.25rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            borderTop: `3px solid ${kpi.color}`,
          }}>
            <p style={{
              margin: '0 0 0.5rem',
              fontSize: '0.8rem',
              color: '#6b7280',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              fontWeight: 600,
            }}>
              {kpi.label}
            </p>
            <p style={{
              margin: 0,
              fontSize: '1.75rem',
              fontWeight: 700,
              color: '#111827',
            }}>
              {formatValue(value, kpi.format)}
            </p>
          </div>
        );
      })}
    </div>
  );
}
