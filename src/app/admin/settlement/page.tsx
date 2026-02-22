'use client';

import { useState, useEffect, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import { useAdmin } from '../context';
import { writeAuditLog } from '@/lib/audit';
import type { SettlementBatch, BatchStatus } from '@/types/database';

export default function SettlementPage() {
  const { t, locale } = useI18n();
  const { can } = useAdmin();
  const [batches, setBatches] = useState<SettlementBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateDate, setGenerateDate] = useState(new Date().toISOString().slice(0, 10));
  const [statusFilter, setStatusFilter] = useState<string>('');

  // Summary
  const [summary, setSummary] = useState({ totalNet: 0, failedCount: 0 });

  const fetchBatches = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    let query = supabase.from('settlement_batches').select('*').order('run_date', { ascending: false }).limit(100);
    if (statusFilter) query = query.eq('status', statusFilter);
    const { data } = await query;
    const list = (data as SettlementBatch[]) ?? [];
    setBatches(list);

    // Compute summary for selected date
    const todayBatches = list.filter((b) => b.run_date === generateDate);
    setSummary({
      totalNet: todayBatches.reduce((sum, b) => sum + Number(b.net_amount), 0),
      failedCount: todayBatches.filter((b) => b.status === 'failed').length,
    });
    setLoading(false);
  }, [statusFilter, generateDate]);

  useEffect(() => { fetchBatches(); }, [fetchBatches]);

  async function handleGenerate() {
    if (!can('settlement.generate')) return;
    setGenerating(true);
    const supabase = createClient();
    const { error } = await supabase.functions.invoke('admin-settlement-generate', {
      body: { run_date: generateDate },
    });
    if (error) {
      alert(error.message || 'Generation failed');
    } else {
      await writeAuditLog({ action: 'settlement.generate_batch', resource_type: 'settlement_batches', metadata: { run_date: generateDate } });
      fetchBatches();
    }
    setGenerating(false);
  }

  async function handleMarkSent(batchId: string) {
    const supabase = createClient();
    await supabase.from('settlement_batches').update({ status: 'processing' }).eq('id', batchId);
    await writeAuditLog({ action: 'settlement.mark_sent', resource_type: 'settlement_batches', resource_id: batchId });
    fetchBatches();
  }

  const fmtCurrency = (val: number) => new Intl.NumberFormat(locale === 'ar' ? 'ar-SA' : 'en-US', { style: 'currency', currency: 'USD' }).format(val);
  const statuses: BatchStatus[] = ['pending', 'processing', 'completed', 'failed'];

  return (
    <div>
      <h1 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 700 }}>
        {locale === 'ar' ? t.settlement.title : 'Settlement Operations'}
      </h1>

      {/* Summary widget */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <div style={{ background: '#fff', borderRadius: '8px', padding: '1rem 1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', flex: 1, minWidth: '200px' }}>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase', fontWeight: 600 }}>
            {locale === 'ar' ? t.settlement.totalNetPayout : 'Total Net Payout'}
          </p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>{fmtCurrency(summary.totalNet)}</p>
        </div>
        <div style={{ background: '#fff', borderRadius: '8px', padding: '1rem 1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', flex: 1, minWidth: '200px' }}>
          <p style={{ margin: 0, fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase', fontWeight: 600 }}>
            {locale === 'ar' ? t.settlement.failedPayouts : 'Failed Payouts'}
          </p>
          <p style={{ margin: '0.25rem 0 0', fontSize: '1.5rem', fontWeight: 700, color: summary.failedCount > 0 ? '#dc2626' : '#111827' }}>{summary.failedCount}</p>
        </div>
      </div>

      {/* Generate batch */}
      {can('settlement.generate') && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input type="date" value={generateDate} onChange={(e) => setGenerateDate(e.target.value)}
            style={{ padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.85rem' }} />
          <button onClick={handleGenerate} disabled={generating}
            style={{ padding: '0.5rem 1rem', background: generating ? '#9ca3af' : '#111827', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
            {generating ? '...' : (locale === 'ar' ? t.settlement.generateBatch : 'Generate Batch')}
          </button>
        </div>
      )}

      {/* Status filter */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <button onClick={() => setStatusFilter('')} style={filterBtn(statusFilter === '')}>{locale === 'ar' ? t.admin.all : 'All'}</button>
        {statuses.map((s) => (
          <button key={s} onClick={() => setStatusFilter(s)} style={filterBtn(statusFilter === s)}>{s}</button>
        ))}
      </div>

      {/* Batch list */}
      {loading ? (
        <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
      ) : batches.length === 0 ? (
        <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.noResults : 'No batches found'}</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={th}>{locale === 'ar' ? t.settlement.runDate : 'Run Date'}</th>
                <th style={th}>{locale === 'ar' ? t.settlement.gross : 'Gross'}</th>
                <th style={th}>{locale === 'ar' ? t.settlement.fees : 'Fees'}</th>
                <th style={th}>{locale === 'ar' ? t.settlement.net : 'Net'}</th>
                <th style={th}>{locale === 'ar' ? t.settlement.itemCount : 'Items'}</th>
                <th style={th}>{locale === 'ar' ? 'الحالة' : 'Status'}</th>
                <th style={th}>{locale === 'ar' ? t.admin.actions : 'Actions'}</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                  <td style={td}>{b.run_date}</td>
                  <td style={td}>{fmtCurrency(b.gross_amount)}</td>
                  <td style={td}>{fmtCurrency(b.total_fees)}</td>
                  <td style={{ ...td, fontWeight: 600 }}>{fmtCurrency(b.net_amount)}</td>
                  <td style={td}>{b.item_count}</td>
                  <td style={td}><Badge value={b.status} /></td>
                  <td style={td}>
                    <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
                      {b.export_url && can('settlement.download') && (
                        <a href={b.export_url} target="_blank" rel="noreferrer" style={actionLink}>
                          {locale === 'ar' ? 'تنزيل' : 'Download'}
                        </a>
                      )}
                      {b.status === 'pending' && can('settlement.mark_sent') && (
                        <button onClick={() => handleMarkSent(b.id)} style={actionBtn}>
                          {locale === 'ar' ? 'تم الإرسال' : 'Mark Sent'}
                        </button>
                      )}
                      <a href={`/admin/settlement/${b.id}/reconcile`} style={actionLink}>
                        {locale === 'ar' ? t.settlement.reconcile : 'Reconcile'}
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    pending: { bg: '#fef9c3', fg: '#854d0e' }, processing: { bg: '#dbeafe', fg: '#1e40af' },
    completed: { bg: '#dcfce7', fg: '#166534' }, failed: { bg: '#fecaca', fg: '#991b1b' },
  };
  const c = colors[value] ?? { bg: '#e5e7eb', fg: '#374151' };
  return <span style={{ padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg }}>{value}</span>;
}

function filterBtn(active: boolean): React.CSSProperties {
  return {
    padding: '0.375rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer',
    border: active ? '2px solid #3b82f6' : '1px solid #d1d5db',
    background: active ? '#eff6ff' : '#fff', color: active ? '#1d4ed8' : '#374151',
    fontWeight: active ? 600 : 400,
  };
}

const th: React.CSSProperties = { textAlign: 'start', padding: '0.5rem 0.75rem', fontSize: '0.7rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' };
const td: React.CSSProperties = { padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: '#111827' };
const actionBtn: React.CSSProperties = { padding: '0.25rem 0.5rem', background: '#111827', color: '#fff', border: 'none', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer' };
const actionLink: React.CSSProperties = { padding: '0.25rem 0.5rem', background: '#f3f4f6', borderRadius: '4px', fontSize: '0.7rem', color: '#3b82f6', textDecoration: 'none' };
