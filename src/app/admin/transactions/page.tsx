'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import type { Transaction, TxType, TxStatus } from '@/types/database';

const TX_TYPES: TxType[] = ['p2p', 'merchant_payment', 'refund', 'deposit', 'withdrawal', 'adjustment'];
const TX_STATUSES: TxStatus[] = ['pending', 'completed', 'failed', 'reversed'];

export default function TransactionsPage() {
  const { t, locale } = useI18n();
  const searchParams = useSearchParams();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTx, setSelectedTx] = useState<Transaction | null>(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [amountMin, setAmountMin] = useState('');
  const [amountMax, setAmountMax] = useState('');
  const [userSearch, setUserSearch] = useState(searchParams.get('user') ?? '');
  const [merchantFilter, setMerchantFilter] = useState('');

  const fetchTransactions = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    let query = supabase.from('transactions').select('*').order('created_at', { ascending: false }).limit(200);

    if (typeFilter) query = query.eq('tx_type', typeFilter);
    if (statusFilter) query = query.eq('status', statusFilter);
    if (dateFrom) query = query.gte('created_at', dateFrom);
    if (dateTo) query = query.lte('created_at', dateTo + 'T23:59:59');
    if (amountMin) query = query.gte('amount', parseFloat(amountMin));
    if (amountMax) query = query.lte('amount', parseFloat(amountMax));
    if (userSearch) query = query.or(`sender_id.eq.${userSearch},receiver_id.eq.${userSearch}`);
    if (merchantFilter) query = query.eq('merchant_id', merchantFilter);

    const { data } = await query;
    setTransactions((data as Transaction[]) ?? []);
    setLoading(false);
  }, [typeFilter, statusFilter, dateFrom, dateTo, amountMin, amountMax, userSearch, merchantFilter]);

  useEffect(() => { fetchTransactions(); }, [fetchTransactions]);

  function exportCsv() {
    if (transactions.length === 0) return;
    const headers = ['ID', 'Type', 'Amount', 'Fee', 'Currency', 'Status', 'Sender', 'Receiver', 'Merchant', 'Created At'];
    const rows = transactions.map((tx) => [tx.id, tx.tx_type, tx.amount, tx.fee, tx.currency, tx.status, tx.sender_id ?? '', tx.receiver_id ?? '', tx.merchant_id ?? '', tx.created_at]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transactions_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const typeLabels: Record<string, string> = locale === 'ar'
    ? { p2p: t.transactions.p2p, merchant_payment: t.transactions.merchantPayment, refund: t.transactions.refund, deposit: t.transactions.deposit, withdrawal: t.transactions.withdrawal, adjustment: t.transactions.adjustment }
    : { p2p: 'P2P', merchant_payment: 'Merchant', refund: 'Refund', deposit: 'Deposit', withdrawal: 'Withdrawal', adjustment: 'Adjustment' };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700 }}>
          {locale === 'ar' ? t.transactions.title : 'Transaction Oversight'}
        </h1>
        <button onClick={exportCsv} disabled={transactions.length === 0} style={{ padding: '0.5rem 1rem', background: '#111827', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer' }}>
          {locale === 'ar' ? t.transactions.exportCsv : 'Export CSV'}
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem', background: '#fff', padding: '1rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={selectStyle}>
          <option value="">{locale === 'ar' ? 'كل الأنواع' : 'All Types'}</option>
          {TX_TYPES.map((t) => <option key={t} value={t}>{typeLabels[t] || t}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={selectStyle}>
          <option value="">{locale === 'ar' ? 'كل الحالات' : 'All Statuses'}</option>
          {TX_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={inputStyle} placeholder="From" />
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={inputStyle} placeholder="To" />
        <input type="number" value={amountMin} onChange={(e) => setAmountMin(e.target.value)} placeholder={locale === 'ar' ? t.transactions.amountMin : 'Min'} style={{ ...inputStyle, width: '80px' }} />
        <input type="number" value={amountMax} onChange={(e) => setAmountMax(e.target.value)} placeholder={locale === 'ar' ? t.transactions.amountMax : 'Max'} style={{ ...inputStyle, width: '80px' }} />
        <input type="text" value={userSearch} onChange={(e) => setUserSearch(e.target.value)} placeholder={locale === 'ar' ? 'معرف المستخدم' : 'User ID'} style={{ ...inputStyle, width: '200px' }} />
      </div>

      {/* Table */}
      {loading ? (
        <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={thS}>ID</th>
                <th style={thS}>{locale === 'ar' ? 'الوقت' : 'Time'}</th>
                <th style={thS}>{locale === 'ar' ? 'النوع' : 'Type'}</th>
                <th style={thS}>{locale === 'ar' ? 'المبلغ' : 'Amount'}</th>
                <th style={thS}>{locale === 'ar' ? 'الرسوم' : 'Fee'}</th>
                <th style={thS}>{locale === 'ar' ? 'الحالة' : 'Status'}</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx) => (
                <tr key={tx.id} onClick={() => setSelectedTx(tx)} style={{ borderTop: '1px solid #e5e7eb', cursor: 'pointer' }}>
                  <td style={{ ...tdS, fontFamily: 'monospace', fontSize: '0.7rem' }}>{tx.id.slice(0, 8)}</td>
                  <td style={tdS}>{new Date(tx.created_at).toLocaleString(locale === 'ar' ? 'ar-SA' : 'en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
                  <td style={tdS}><span style={{ background: '#f3f4f6', padding: '0.125rem 0.375rem', borderRadius: '4px', fontSize: '0.7rem' }}>{typeLabels[tx.tx_type] || tx.tx_type}</span></td>
                  <td style={tdS}>{tx.currency} {tx.amount.toFixed(2)}</td>
                  <td style={tdS}>{tx.fee > 0 ? tx.fee.toFixed(2) : '-'}</td>
                  <td style={tdS}><StatusBadge value={tx.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#6b7280' }}>
            {locale === 'ar' ? `${transactions.length} نتيجة` : `${transactions.length} results`}
          </p>
        </div>
      )}

      {/* Transaction detail modal */}
      {selectedTx && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }} onClick={() => setSelectedTx(null)}>
          <div style={{ background: '#fff', borderRadius: '12px', padding: '1.5rem', maxWidth: '500px', width: '90%', maxHeight: '80vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>{locale === 'ar' ? t.admin.details : 'Transaction Detail'}</h2>
              <button onClick={() => setSelectedTx(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem' }}>{'\u2715'}</button>
            </div>
            <DetailRow label="ID" value={selectedTx.id} mono />
            <DetailRow label={locale === 'ar' ? 'النوع' : 'Type'} value={typeLabels[selectedTx.tx_type] || selectedTx.tx_type} />
            <DetailRow label={locale === 'ar' ? 'المبلغ' : 'Amount'} value={`${selectedTx.currency} ${selectedTx.amount.toFixed(2)}`} />
            <DetailRow label={locale === 'ar' ? 'الرسوم' : 'Fee'} value={selectedTx.fee > 0 ? `${selectedTx.currency} ${selectedTx.fee.toFixed(2)}` : '-'} />
            <DetailRow label={locale === 'ar' ? 'الحالة' : 'Status'} value={<StatusBadge value={selectedTx.status} />} />
            <DetailRow label={locale === 'ar' ? 'التاريخ' : 'Date'} value={new Date(selectedTx.created_at).toLocaleString()} />
            {selectedTx.sender_id && <DetailRow label={locale === 'ar' ? 'المرسل' : 'Sender'} value={<a href={`/admin/users?selected=${selectedTx.sender_id}`} style={{ color: '#3b82f6' }}>{selectedTx.sender_id.slice(0, 12)}...</a>} />}
            {selectedTx.receiver_id && <DetailRow label={locale === 'ar' ? 'المستلم' : 'Receiver'} value={<a href={`/admin/users?selected=${selectedTx.receiver_id}`} style={{ color: '#3b82f6' }}>{selectedTx.receiver_id.slice(0, 12)}...</a>} />}
            {selectedTx.merchant_id && <DetailRow label={locale === 'ar' ? 'التاجر' : 'Merchant'} value={selectedTx.merchant_id.slice(0, 12)} />}
            {selectedTx.reference_tx_id && <DetailRow label={locale === 'ar' ? t.transactions.originalTx : 'Original TX'} value={selectedTx.reference_tx_id.slice(0, 12)} />}
            {selectedTx.metadata && Object.keys(selectedTx.metadata).length > 0 && (
              <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: '#f9fafb', borderRadius: '6px', fontSize: '0.75rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {JSON.stringify(selectedTx.metadata, null, 2)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.375rem 0', borderBottom: '1px solid #f3f4f6', fontSize: '0.85rem' }}>
      <span style={{ color: '#6b7280' }}>{label}</span>
      <span style={{ color: '#111827', fontFamily: mono ? 'monospace' : 'inherit', fontSize: mono ? '0.75rem' : undefined }}>{value}</span>
    </div>
  );
}

function StatusBadge({ value }: { value: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    completed: { bg: '#dcfce7', fg: '#166534' }, pending: { bg: '#fef9c3', fg: '#854d0e' },
    failed: { bg: '#fecaca', fg: '#991b1b' }, reversed: { bg: '#e9d5ff', fg: '#6b21a8' },
  };
  const c = colors[value] ?? { bg: '#e5e7eb', fg: '#374151' };
  return <span style={{ display: 'inline-block', padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg }}>{value}</span>;
}

const selectStyle: React.CSSProperties = { padding: '0.375rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.8rem', background: '#fff' };
const inputStyle: React.CSSProperties = { padding: '0.375rem 0.5rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.8rem' };
const thS: React.CSSProperties = { textAlign: 'start', padding: '0.5rem 0.75rem', fontSize: '0.7rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' };
const tdS: React.CSSProperties = { padding: '0.5rem 0.75rem', fontSize: '0.8rem', color: '#111827' };
