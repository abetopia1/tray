'use client';

import { useEffect, useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import type { QueueCounts } from '@/types/database';

export default function ActionQueues({ refreshKey }: { refreshKey?: number }) {
  const { t, locale } = useI18n();
  const [counts, setCounts] = useState<QueueCounts | null>(null);
  const [loading, setLoading] = useState(true);

  const QUEUES = [
    { key: 'kyc_pending' as const, label: locale === 'ar' ? t.queues.kycPending : 'KYC Pending', href: '/admin/kyc', color: '#f59e0b', desc: locale === 'ar' ? 'بانتظار مراجعة الهوية' : 'Awaiting identity review' },
    { key: 'merchant_pending' as const, label: locale === 'ar' ? t.queues.merchantPending : 'Merchants Pending', href: '/admin/users?filter=pending_merchants', color: '#8b5cf6', desc: locale === 'ar' ? 'طلبات تاجر جديدة' : 'New merchant applications' },
    { key: 'settlement_batches' as const, label: locale === 'ar' ? t.queues.settlementPending : 'Settlement Batches', href: '/admin/settlement', color: '#3b82f6', desc: locale === 'ar' ? 'دفعات معلقة' : 'Pending batch payouts' },
    { key: 'reconciliation_exceptions' as const, label: locale === 'ar' ? t.queues.reconExceptions : 'Recon Exceptions', href: '/admin/settlement', color: '#ef4444', desc: locale === 'ar' ? 'استثناءات مفتوحة' : 'Open exceptions' },
    { key: 'support_tickets' as const, label: locale === 'ar' ? t.queues.openTickets : 'Open Tickets', href: '/admin/support', color: '#10b981', desc: locale === 'ar' ? 'تذاكر تحتاج رد' : 'Tickets needing response' },
  ];

  const fetchCounts = useCallback(async () => {
    setLoading(true);
    try {
      const supabase = createClient();
      const [kyc, merchants, settlements, recon, tickets] = await Promise.all([
        supabase.from('kyc_reviews').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
        supabase.from('merchant_profiles').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
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
    } catch { /* counts show as 0 */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchCounts(); }, [fetchCounts, refreshKey]);

  return (
    <div>
      <h2 style={{ margin: '0 0 1rem', fontSize: '1.125rem', fontWeight: 600, color: '#111827' }}>
        {locale === 'ar' ? t.queues.title : 'Action Queues'}
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.75rem' }}>
        {QUEUES.map((queue) => {
          const count = counts?.[queue.key] ?? 0;
          return (
            <a key={queue.key} href={queue.href} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: '#fff', borderRadius: '8px', padding: '1rem 1.25rem',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)', textDecoration: 'none', color: 'inherit',
              borderInlineStart: `4px solid ${queue.color}`,
            }}>
              <div>
                <p style={{ margin: 0, fontWeight: 600, fontSize: '0.9rem', color: '#111827' }}>{queue.label}</p>
                <p style={{ margin: '0.125rem 0 0', fontSize: '0.75rem', color: '#6b7280' }}>{queue.desc}</p>
              </div>
              <div style={{
                minWidth: '40px', height: '40px', borderRadius: '50%',
                background: loading ? '#e5e7eb' : (count > 0 ? queue.color : '#e5e7eb'),
                color: count > 0 ? '#fff' : '#6b7280',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: '0.9rem', flexShrink: 0, marginInlineStart: '1rem',
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
