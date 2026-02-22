'use client';

import { useState, useEffect, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import { useAdmin } from '../context';
import { writeAuditLog } from '@/lib/audit';
import type { KycReview, KycStatus } from '@/types/database';

const STATUS_FILTERS: KycStatus[] = ['pending', 'resubmission_required', 'rejected', 'approved'];

function timeSince(dateStr: string, locale: string): string {
  const ms = Date.now() - new Date(dateStr).getTime();
  const hours = Math.floor(ms / 3600000);
  if (hours < 24) return locale === 'ar' ? `${hours} ساعة` : `${hours}h`;
  const days = Math.floor(hours / 24);
  return locale === 'ar' ? `${days} يوم` : `${days}d`;
}

export default function KycPage() {
  const { t, locale } = useI18n();
  const { can } = useAdmin();
  const [reviews, setReviews] = useState<KycReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selected, setSelected] = useState<KycReview | null>(null);

  // Decision form
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectNotes, setRejectNotes] = useState('');
  const [resubmitReason, setResubmitReason] = useState('');

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    let query = supabase.from('kyc_reviews').select('*').order('submitted_at', { ascending: false }).limit(100);
    if (statusFilter) query = query.eq('status', statusFilter);
    const { data } = await query;
    setReviews((data as KycReview[]) ?? []);
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => { fetchReviews(); }, [fetchReviews]);

  async function handleDecision(action: 'approve' | 'reject' | 'resubmit') {
    if (!selected) return;
    setDecisionLoading(true);
    const supabase = createClient();

    if (action === 'approve') {
      await supabase.from('kyc_reviews').update({ status: 'approved' }).eq('id', selected.id);
      await supabase.from('profiles').update({ kyc_status: 'approved' }).eq('id', selected.user_id);
      await writeAuditLog({ action: 'kyc.approve', resource_type: 'kyc_reviews', resource_id: selected.id });
    } else if (action === 'reject') {
      if (!rejectReason) { setDecisionLoading(false); return; }
      await supabase.from('kyc_reviews').update({ status: 'rejected', reason_code: rejectReason, notes: rejectNotes }).eq('id', selected.id);
      await supabase.from('profiles').update({ kyc_status: 'rejected' }).eq('id', selected.user_id);
      await writeAuditLog({ action: 'kyc.reject', resource_type: 'kyc_reviews', resource_id: selected.id, metadata: { reason_code: rejectReason, notes: rejectNotes } });
    } else if (action === 'resubmit') {
      if (!resubmitReason) { setDecisionLoading(false); return; }
      await supabase.from('kyc_reviews').update({ status: 'resubmission_required', reason_code: resubmitReason }).eq('id', selected.id);
      await supabase.from('profiles').update({ kyc_status: 'resubmission_required' }).eq('id', selected.user_id);
      await writeAuditLog({ action: 'kyc.request_resubmission', resource_type: 'kyc_reviews', resource_id: selected.id, metadata: { reason: resubmitReason } });
    }

    setSelected(null);
    setRejectReason('');
    setRejectNotes('');
    setResubmitReason('');
    setDecisionLoading(false);
    fetchReviews();
  }

  const canDecide = can('kyc.approve');

  return (
    <div style={{ display: 'flex', gap: '1.5rem' }}>
      {/* Queue list */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 700 }}>
          {locale === 'ar' ? t.kyc.title : 'KYC Review Queue'}
        </h1>

        {/* Status filter */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          {STATUS_FILTERS.map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)} style={{
              padding: '0.375rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer',
              border: statusFilter === s ? '2px solid #3b82f6' : '1px solid #d1d5db',
              background: statusFilter === s ? '#eff6ff' : '#fff', color: statusFilter === s ? '#1d4ed8' : '#374151',
              fontWeight: statusFilter === s ? 600 : 400,
            }}>
              {s.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        {loading ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
        ) : reviews.length === 0 ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.noResults : 'No reviews found'}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={th}>{locale === 'ar' ? 'الاسم' : 'Name'}</th>
                  <th style={th}>{locale === 'ar' ? 'رقم الهوية' : 'National ID'}</th>
                  <th style={th}>{locale === 'ar' ? 'الحالة' : 'Status'}</th>
                  <th style={th}>{locale === 'ar' ? 'معلق منذ' : 'Pending'}</th>
                  <th style={th}>SLA</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((r) => {
                  const pendingHours = Math.floor((Date.now() - new Date(r.submitted_at).getTime()) / 3600000);
                  const slaWarning = r.status === 'pending' && pendingHours > 24;
                  return (
                    <tr key={r.id} onClick={() => setSelected(r)} style={{ borderTop: '1px solid #e5e7eb', cursor: 'pointer', background: selected?.id === r.id ? '#eff6ff' : 'transparent' }}>
                      <td style={td}>{r.full_name || '-'}</td>
                      <td style={{ ...td, fontFamily: 'monospace', fontSize: '0.8rem' }}>{r.national_id || '-'}</td>
                      <td style={td}><Badge value={r.status} /></td>
                      <td style={td}>{timeSince(r.submitted_at, locale)}</td>
                      <td style={td}>
                        {slaWarning && <span style={{ color: '#dc2626', fontWeight: 700, fontSize: '0.7rem' }}>{locale === 'ar' ? 'تحذير!' : 'OVERDUE'}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <div style={{ width: '380px', flexShrink: 0, background: '#fff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '1.25rem', overflowY: 'auto', maxHeight: 'calc(100vh - 4rem)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>{locale === 'ar' ? 'مراجعة KYC' : 'KYC Review'}</h2>
            <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: '#6b7280' }}>{'\u2715'}</button>
          </div>

          <DetailRow label={locale === 'ar' ? 'الاسم الكامل' : 'Full Name'} value={selected.full_name} />
          <DetailRow label={locale === 'ar' ? t.kyc.nationalId : 'National ID'} value={selected.national_id} mono />
          <DetailRow label={locale === 'ar' ? t.kyc.dob : 'Date of Birth'} value={selected.dob} />
          <DetailRow label={locale === 'ar' ? 'الحالة' : 'Status'} value={<Badge value={selected.status} />} />
          <DetailRow label={locale === 'ar' ? 'تاريخ التقديم' : 'Submitted'} value={new Date(selected.submitted_at).toLocaleString()} />

          {selected.selfie_path && (
            <div style={{ margin: '0.75rem 0' }}>
              <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>{locale === 'ar' ? t.kyc.selfie : 'Selfie'}</p>
              <div style={{ background: '#f3f4f6', borderRadius: '8px', padding: '2rem', textAlign: 'center', fontSize: '0.8rem', color: '#6b7280' }}>
                {locale === 'ar' ? 'معاينة عبر رابط موقع' : 'Preview via signed URL'}
              </div>
            </div>
          )}

          {selected.notes && <DetailRow label={locale === 'ar' ? 'ملاحظات' : 'Notes'} value={selected.notes} />}
          {selected.reason_code && <DetailRow label={locale === 'ar' ? 'رمز السبب' : 'Reason'} value={selected.reason_code} />}

          {/* Decision actions */}
          {canDecide && selected.status === 'pending' && (
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #e5e7eb' }}>
              <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', fontWeight: 600 }}>{locale === 'ar' ? t.admin.actions : 'Actions'}</h3>

              <button onClick={() => handleDecision('approve')} disabled={decisionLoading}
                style={{ width: '100%', padding: '0.5rem', background: '#10b981', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', marginBottom: '0.5rem' }}>
                {locale === 'ar' ? t.kyc.approve : 'Approve'}
              </button>

              <div style={{ marginBottom: '0.5rem' }}>
                <input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder={locale === 'ar' ? t.kyc.reasonCode : 'Reason code'} style={{ ...inp, marginBottom: '0.25rem' }} />
                <input value={rejectNotes} onChange={(e) => setRejectNotes(e.target.value)} placeholder={locale === 'ar' ? t.kyc.reviewerNotes : 'Notes (optional)'} style={inp} />
                <button onClick={() => handleDecision('reject')} disabled={decisionLoading || !rejectReason}
                  style={{ width: '100%', padding: '0.5rem', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', marginTop: '0.25rem', opacity: rejectReason ? 1 : 0.5 }}>
                  {locale === 'ar' ? t.kyc.reject : 'Reject'}
                </button>
              </div>

              <div>
                <input value={resubmitReason} onChange={(e) => setResubmitReason(e.target.value)} placeholder={locale === 'ar' ? 'سبب إعادة التقديم' : 'Resubmission reason'} style={inp} />
                <button onClick={() => handleDecision('resubmit')} disabled={decisionLoading || !resubmitReason}
                  style={{ width: '100%', padding: '0.5rem', background: '#f59e0b', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', marginTop: '0.25rem', opacity: resubmitReason ? 1 : 0.5 }}>
                  {locale === 'ar' ? t.kyc.requestResubmission : 'Request Resubmission'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.375rem 0', borderBottom: '1px solid #f3f4f6', fontSize: '0.85rem' }}>
      <span style={{ color: '#6b7280' }}>{label}</span>
      <span style={{ color: '#111827', fontFamily: mono ? 'monospace' : 'inherit' }}>{value ?? '-'}</span>
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    approved: { bg: '#dcfce7', fg: '#166534' }, pending: { bg: '#fef9c3', fg: '#854d0e' },
    rejected: { bg: '#fecaca', fg: '#991b1b' }, resubmission_required: { bg: '#fed7aa', fg: '#9a3412' },
  };
  const c = colors[value] ?? { bg: '#e5e7eb', fg: '#374151' };
  return <span style={{ padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg }}>{value.replace(/_/g, ' ')}</span>;
}

const th: React.CSSProperties = { textAlign: 'start', padding: '0.5rem 0.75rem', fontSize: '0.7rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' };
const td: React.CSSProperties = { padding: '0.5rem 0.75rem', fontSize: '0.85rem', color: '#111827' };
const inp: React.CSSProperties = { width: '100%', padding: '0.375rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.8rem', boxSizing: 'border-box' };
