'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { QueueCounts } from '@/types/database';

const QUEUES = [
  {
    key: 'kyc_pending',
    label: 'KYC Pending',
    href: '/admin/kyc',
    color: '#f59e0b',
    description: 'Users awaiting identity verification',
  },
  {
    key: 'merchant_pending',
    label: 'Merchant Pending',
    href: '/admin/merchants',
    color: '#8b5cf6',
    description: 'Merchant applications awaiting review',
  },
  {
    key: 'settlement_batches',
    label: 'Settlement Batches',
    href: '/admin/settlement',
    color: '#3b82f6',
    description: 'Pending settlement batches',
  },
  {
    key: 'reconciliation_exceptions',
    label: 'Recon Exceptions',
    href: '/admin/reconciliation',
    color: '#ef4444',
    description: 'Open reconciliation exceptions',
  },
  {
    key: 'support_tickets',
    label: 'Support Tickets',
    href: '/admin/support',
    color: '#10b981',
    description: 'Open support tickets',
  },
] as const;

export default function ActionQueues() {
  const [counts, setCounts] = useState<QueueCounts | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchCounts() {
      try {
        const supabase = createClient();

        const [kyc, merchants, settlements, recon, tickets] = await Promise.all([
          supabase.from('kyc_reviews').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
          supabase.from('merchants').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
          supabase.from('settlement_batches').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
          supabase.from('reconciliation_exceptions').select('id', { count: 'exact', head: true }).eq('status', 'open'),
          supabase.from('support_tickets').select('id', { count: 'exact', head: true }).in('status', ['open', 'in_progress']),
        ]);

        setCounts({
          kyc_pending: kyc.count ?? 0,
          merchant_pending: merchants.count ?? 0,
          settlement_batches: settlements.count ?? 0,
          reconciliation_exceptions: recon.count ?? 0,
          support_tickets: tickets.count ?? 0,
        });
      } catch {
        // Counts will show as 0 on error
      } finally {
        setLoading(false);
      }
    }

    fetchCounts();
  }, []);

  return (
    <div>
      <h2 style={{ margin: '0 0 1rem', fontSize: '1.125rem', fontWeight: 600, color: '#111827' }}>
        Action Queues
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
        {QUEUES.map((queue) => {
          const count = counts?.[queue.key] ?? 0;
          return (
            <a
              key={queue.key}
              href={queue.href}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#fff',
                borderRadius: '8px',
                padding: '1rem 1.25rem',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                textDecoration: 'none',
                color: 'inherit',
                borderLeft: `4px solid ${queue.color}`,
                transition: 'box-shadow 0.15s',
              }}
            >
              <div>
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9rem', color: '#111827' }}>
                  {queue.label}
                </p>
                <p style={{ margin: '0.125rem 0 0', fontSize: '0.75rem', color: '#6b7280' }}>
                  {queue.description}
                </p>
              </div>
              <div style={{
                minWidth: '40px',
                height: '40px',
                borderRadius: '50%',
                background: loading ? '#e5e7eb' : (count > 0 ? queue.color : '#e5e7eb'),
                color: count > 0 ? '#fff' : '#6b7280',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.9rem',
                flexShrink: 0,
                marginLeft: '1rem',
              }}>
                {loading ? '...' : count}
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
}
