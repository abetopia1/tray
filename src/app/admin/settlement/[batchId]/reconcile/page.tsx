'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import { useAdmin } from '../../../context';
import { writeAuditLog } from '@/lib/audit';
import type { PayoutItem, ReconciliationException } from '@/types/database';

export default function ReconcilePage() {
  const { t, locale } = useI18n();
  const { can } = useAdmin();
  const { batchId } = useParams<{ batchId: string }>();

  const [payoutItems, setPayoutItems] = useState<PayoutItem[]>([]);
  const [exceptions, setExceptions] = useState<ReconciliationException[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Stats
  const [stats, setStats] = useState({ matched: 0, unmatched: 0, failed: 0 });

  const fetchData = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    const [itemsRes, exceptionsRes] = await Promise.all([
      supabase.from('payout_items').select('*').eq('batch_id', batchId).order('created_at', { ascending: false }),
      supabase.from('reconciliation_exceptions').select('*').eq('batch_id', batchId).order('created_at', { ascending: false }),
    ]);
    const items = (itemsRes.data as PayoutItem[]) ?? [];
    const excs = (exceptionsRes.data as ReconciliationException[]) ?? [];
    setPayoutItems(items);
    setExceptions(excs);
    setStats({
      matched: items.filter((i) => i.status === 'confirmed').length,
      unmatched: items.filter((i) => i.status === 'pending').length,
      failed: items.filter((i) => i.status === 'failed').length,
    });
    setLoading(false);
  }, [batchId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !can('recon.upload')) return;
    setUploading(true);

    const text = await file.text();
    const supabase = createClient();
    const { error } = await supabase.functions.invoke('admin-reconcile-upload', {
      body: { batch_id: batchId, csv_content: text },
    });

    if (error) {
      alert(error.message || 'Upload failed');
    } else {
      await writeAuditLog({ action: 'recon.upload', resource_type: 'settlement_batches', resource_id: batchId });
      fetchData();
    }
    setUploading(false);
    e.target.value = '';
  }

  async function handleResolve(exceptionId: string, notes: string) {
    if (!notes) return;
    const supabase = createClient();
    await supabase.from('reconciliation_exceptions').update({ status: 'resolved', resolution_notes: notes, resolved_at: new Date().toISOString() }).eq('id', exceptionId);
    await writeAuditLog({ action: 'recon.resolve', resource_type: 'reconciliation_exceptions', resource_id: exceptionId, metadata: { notes } });
    fetchData();
  }

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <a href="/admin/settlement" style={{ color: '#3b82f6', fontSize: '0.85rem', textDecoration: 'none' }}>
          {locale === 'ar' ? '← العودة للتسوية' : '← Back to Settlement'}
        </a>
      </div>

      <h1 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 700 }}>
        {locale === 'ar' ? t.reconciliation.title : 'Reconciliation'} — {batchId.slice(0, 8)}
      </h1>

      {/* Stats */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <StatCard label={locale === 'ar' ? t.reconciliation.matched : 'Matched'} value={stats.matched} color="#10b981" />
        <StatCard label={locale === 'ar' ? t.reconciliation.unmatched : 'Unmatched'} value={stats.unmatched} color="#f59e0b" />
        <StatCard label={locale === 'ar' ? t.reconciliation.failedItems : 'Failed'} value={stats.failed} color="#ef4444" />
      </div>

      {/* Upload */}
      {can('recon.upload') && (
        <div style={{ marginBottom: '1.5rem', background: '#fff', padding: '1rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
          <p style={{ margin: '0 0 0.5rem', fontWeight: 600, fontSize: '0.85rem' }}>
            {locale === 'ar' ? t.reconciliation.uploadFile : 'Upload Bank Confirmation (CSV)'}
          </p>
          <input
            type="file"
            accept=".csv"
            onChange={handleUpload}
            disabled={uploading}
            style={{ fontSize: '0.85rem' }}
          />
          {uploading && <p style={{ marginTop: '0.25rem', fontSize: '0.8rem', color: '#6b7280' }}>{locale === 'ar' ? 'جارٍ المعالجة...' : 'Processing...'}</p>}
        </div>
      )}

      {loading ? (
        <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
      ) : (
        <>
          {/* Payout items */}
          {payoutItems.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600 }}>
                {locale === 'ar' ? 'عناصر الدفع' : 'Payout Items'} ({payoutItems.length})
              </h2>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                  <thead>
                    <tr style={{ background: '#f9fafb' }}>
                      <th style={th}>{locale === 'ar' ? 'المرجع' : 'Reference'}</th>
                      <th style={th}>{locale === 'ar' ? 'التاجر' : 'Merchant'}</th>
                      <th style={th}>{locale === 'ar' ? 'المبلغ' : 'Amount'}</th>
                      <th style={th}>{locale === 'ar' ? 'الحالة' : 'Status'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payoutItems.map((item) => (
                      <tr key={item.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                        <td style={{ ...td, fontFamily: 'monospace', fontSize: '0.75rem' }}>{item.reference}</td>
                        <td style={td}>{item.merchant_id.slice(0, 8)}</td>
                        <td style={td}>${Number(item.amount).toFixed(2)}</td>
                        <td style={td}><Badge value={item.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Exceptions queue */}
          {exceptions.length > 0 && (
            <div>
              <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem', fontWeight: 600, color: '#dc2626' }}>
                {locale === 'ar' ? 'الاستثناءات' : 'Exceptions'} ({exceptions.length})
              </h2>
              {exceptions.map((exc) => (
                <ExceptionCard key={exc.id} exception={exc} locale={locale} onResolve={handleResolve} canResolve={can('recon.resolve')} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: '#fff', borderRadius: '8px', padding: '0.75rem 1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', borderTop: `3px solid ${color}`, minWidth: '120px' }}>
      <p style={{ margin: 0, fontSize: '0.7rem', color: '#6b7280', textTransform: 'uppercase', fontWeight: 600 }}>{label}</p>
      <p style={{ margin: '0.125rem 0 0', fontSize: '1.25rem', fontWeight: 700 }}>{value}</p>
    </div>
  );
}

function ExceptionCard({ exception, locale, onResolve, canResolve }: { exception: ReconciliationException; locale: string; onResolve: (id: string, notes: string) => void; canResolve: boolean }) {
  const [notes, setNotes] = useState('');

  return (
    <div style={{ background: '#fff', borderRadius: '8px', padding: '1rem', marginBottom: '0.5rem', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', borderInlineStart: `4px solid ${exception.status === 'resolved' ? '#10b981' : '#ef4444'}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.375rem' }}>
        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{exception.reason}</span>
        <Badge value={exception.status} />
      </div>
      {exception.resolution_notes && <p style={{ margin: '0.25rem 0', fontSize: '0.8rem', color: '#6b7280' }}>{exception.resolution_notes}</p>}
      {exception.status !== 'resolved' && canResolve && (
        <div style={{ display: 'flex', gap: '0.375rem', marginTop: '0.5rem' }}>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder={locale === 'ar' ? 'ملاحظات الحل' : 'Resolution notes'} style={{ flex: 1, padding: '0.375rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.8rem' }} />
          <button onClick={() => { onResolve(exception.id, notes); setNotes(''); }} disabled={!notes} style={{ padding: '0.375rem 0.75rem', background: notes ? '#10b981' : '#d1d5db', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '0.75rem', cursor: notes ? 'pointer' : 'not-allowed' }}>
            {locale === 'ar' ? 'حل' : 'Resolve'}
          </button>
        </div>
      )}
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    pending: { bg: '#fef9c3', fg: '#854d0e' }, confirmed: { bg: '#dcfce7', fg: '#166534' },
    failed: { bg: '#fecaca', fg: '#991b1b' }, open: { bg: '#fecaca', fg: '#991b1b' },
    investigating: { bg: '#dbeafe', fg: '#1e40af' }, resolved: { bg: '#dcfce7', fg: '#166534' },
  };
  const c = colors[value] ?? { bg: '#e5e7eb', fg: '#374151' };
  return <span style={{ padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg }}>{value}</span>;
}

const th: React.CSSProperties = { textAlign: 'start', padding: '0.5rem 0.75rem', fontSize: '0.7rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' };
const td: React.CSSProperties = { padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: '#111827' };
