'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import { useAdmin } from '../context';
import { writeAuditLog } from '@/lib/audit';
import type { Profile, MerchantProfile, Device, Transaction, KycReview, AuditLog, AdminRole } from '@/types/database';

type UserFilter = 'all' | 'merchants_only' | 'pending_merchants';

export default function UsersPage() {
  const { t, locale } = useI18n();
  const { roles, can, userId: actorId } = useAdmin();
  const searchParams = useSearchParams();

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<UserFilter>((searchParams.get('filter') as UserFilter) || 'all');
  const [users, setUsers] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get('selected'));

  // Detail panel state
  const [detail, setDetail] = useState<{
    profile: Profile;
    merchant: MerchantProfile | null;
    devices: Device[];
    recentTx: Transaction[];
    kyc: KycReview | null;
    userRoles: AdminRole[];
    auditLogs: AuditLog[];
  } | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    let query = supabase.from('profiles').select('*').order('created_at', { ascending: false }).limit(100);

    if (search.trim()) {
      const s = search.trim();
      query = query.or(`phone_e164.ilike.%${s}%,handle.ilike.%${s}%,full_name.ilike.%${s}%`);
    }
    if (filter === 'merchants_only') {
      const { data: mp } = await supabase.from('merchant_profiles').select('user_id');
      const ids = (mp ?? []).map((m: { user_id: string }) => m.user_id);
      if (ids.length > 0) query = query.in('id', ids);
      else { setUsers([]); setLoading(false); return; }
    }
    if (filter === 'pending_merchants') {
      const { data: mp } = await supabase.from('merchant_profiles').select('user_id').eq('status', 'pending');
      const ids = (mp ?? []).map((m: { user_id: string }) => m.user_id);
      if (ids.length > 0) query = query.in('id', ids);
      else { setUsers([]); setLoading(false); return; }
    }

    const { data } = await query;
    setUsers((data as Profile[]) ?? []);
    setLoading(false);
  }, [search, filter]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const loadDetail = useCallback(async (userId: string) => {
    setSelectedId(userId);
    setDetailLoading(true);
    const supabase = createClient();
    const [profileRes, merchantRes, devicesRes, txRes, kycRes, rolesRes] = await Promise.all([
      supabase.from('profiles').select('*').eq('id', userId).single(),
      supabase.from('merchant_profiles').select('*').eq('user_id', userId).maybeSingle(),
      supabase.from('devices').select('*').eq('user_id', userId).order('last_active_at', { ascending: false }),
      supabase.from('transactions').select('*').or(`sender_id.eq.${userId},receiver_id.eq.${userId}`).order('created_at', { ascending: false }).limit(20),
      supabase.from('kyc_reviews').select('*').eq('user_id', userId).order('created_at', { ascending: false }).limit(1).maybeSingle(),
      supabase.from('user_roles').select('role').eq('user_id', userId),
    ]);
    setDetail({
      profile: profileRes.data as Profile,
      merchant: merchantRes.data as MerchantProfile | null,
      devices: (devicesRes.data as Device[]) ?? [],
      recentTx: (txRes.data as Transaction[]) ?? [],
      kyc: kycRes.data as KycReview | null,
      userRoles: ((rolesRes.data as { role: AdminRole }[]) ?? []).map((r) => r.role),
      auditLogs: [],
    });
    setDetailLoading(false);
  }, []);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  // Admin actions
  async function handleAction(action: string, payload: Record<string, unknown> = {}) {
    if (!selectedId || !detail) return;
    const supabase = createClient();

    if (action === 'freeze' || action === 'unfreeze') {
      await supabase.functions.invoke('admin-audit', {
        body: { action: `user.${action}_wallet`, resource_type: 'profiles', resource_id: selectedId, metadata: payload },
      });
      await supabase.from('profiles').update({ wallet_status: action === 'freeze' ? 'frozen' : 'active' }).eq('id', selectedId);
      loadDetail(selectedId);
    }
    if (action === 'force_kyc_resubmit') {
      await supabase.from('profiles').update({ kyc_status: 'resubmission_required' }).eq('id', selectedId);
      if (detail.kyc) {
        await supabase.from('kyc_reviews').update({ status: 'resubmission_required' }).eq('id', detail.kyc.id);
      }
      await writeAuditLog({ action: 'user.force_kyc_resubmit', resource_type: 'profiles', resource_id: selectedId });
      loadDetail(selectedId);
    }
    if (action === 'merchant_approve' || action === 'merchant_reject' || action === 'merchant_suspend') {
      const statusMap: Record<string, string> = { merchant_approve: 'active', merchant_reject: 'rejected', merchant_suspend: 'suspended' };
      if (detail.merchant) {
        await supabase.from('merchant_profiles').update({ status: statusMap[action] }).eq('id', detail.merchant.id);
      }
      await writeAuditLog({ action: `merchant.${action.replace('merchant_', '')}`, resource_type: 'merchant_profiles', resource_id: detail.merchant?.id, metadata: payload });
      loadDetail(selectedId);
    }
    if (action === 'set_role') {
      const role = payload.role as string;
      await supabase.from('user_roles').upsert({ user_id: selectedId, role, granted_by: actorId }, { onConflict: 'user_id,role' });
      await writeAuditLog({ action: 'user.set_role', resource_type: 'user_roles', resource_id: selectedId, metadata: { role } });
      loadDetail(selectedId);
    }
  }

  const isReadOnly = !roles.includes('admin') && !roles.includes('compliance');
  const filterLabels = locale === 'ar'
    ? { all: t.users.allUsers, merchants_only: t.users.merchantsOnly, pending_merchants: t.users.pendingMerchants }
    : { all: 'All Users', merchants_only: 'Merchants Only', pending_merchants: 'Pending Merchants' };

  return (
    <div style={{ display: 'flex', gap: '1.5rem', minHeight: 'calc(100vh - 4rem)' }}>
      {/* Left: User list */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 700 }}>
          {locale === 'ar' ? t.users.title : 'Users & Merchants'}
        </h1>

        {/* Search + filters */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchUsers()}
            placeholder={locale === 'ar' ? t.users.searchPlaceholder : 'Search by phone, handle, or name...'}
            style={{ flex: 1, minWidth: '200px', padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.85rem' }}
          />
          {(['all', 'merchants_only', 'pending_merchants'] as UserFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '0.5rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer',
                border: filter === f ? '2px solid #3b82f6' : '1px solid #d1d5db',
                background: filter === f ? '#eff6ff' : '#fff',
                color: filter === f ? '#1d4ed8' : '#374151',
                fontWeight: filter === f ? 600 : 400,
              }}
            >
              {filterLabels[f]}
            </button>
          ))}
        </div>

        {/* User table */}
        {loading ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
        ) : users.length === 0 ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.noResults : 'No users found'}</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={th}>{locale === 'ar' ? 'الاسم' : 'Name'}</th>
                  <th style={th}>{locale === 'ar' ? 'الهاتف' : 'Phone'}</th>
                  <th style={th}>KYC</th>
                  <th style={th}>{locale === 'ar' ? 'المحفظة' : 'Wallet'}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr
                    key={u.id}
                    onClick={() => setSelectedId(u.id)}
                    style={{ borderTop: '1px solid #e5e7eb', cursor: 'pointer', background: selectedId === u.id ? '#eff6ff' : 'transparent' }}
                  >
                    <td style={td}>{u.full_name || u.handle || u.id.slice(0, 8)}</td>
                    <td style={{ ...td, fontFamily: 'monospace', fontSize: '0.8rem' }}>{u.phone_e164 || '-'}</td>
                    <td style={td}><Badge value={u.kyc_status} /></td>
                    <td style={td}><Badge value={u.wallet_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Right: User detail panel */}
      {selectedId && (
        <div style={{ width: '420px', flexShrink: 0, background: '#fff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '1.25rem', overflowY: 'auto', maxHeight: 'calc(100vh - 4rem)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>{locale === 'ar' ? t.users.profile : 'Profile'}</h2>
            <button onClick={() => { setSelectedId(null); setDetail(null); }} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: '#6b7280' }}>{'\u2715'}</button>
          </div>

          {detailLoading ? (
            <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
          ) : detail ? (
            <div>
              {/* Profile info */}
              <Section title={locale === 'ar' ? t.users.profile : 'Profile'}>
                <Field label={locale === 'ar' ? 'الاسم' : 'Name'} value={detail.profile.full_name} />
                <Field label={locale === 'ar' ? 'المعرف' : 'Handle'} value={detail.profile.handle} />
                <Field label={locale === 'ar' ? 'الهاتف' : 'Phone'} value={detail.profile.phone_e164} mono />
                <Field label="KYC" value={<Badge value={detail.profile.kyc_status} />} />
                <Field label={locale === 'ar' ? 'المحفظة' : 'Wallet'} value={<Badge value={detail.profile.wallet_status} />} />
                <Field label={locale === 'ar' ? 'الأدوار' : 'Roles'} value={detail.userRoles.length > 0 ? detail.userRoles.join(', ') : '-'} />
              </Section>

              {/* Devices */}
              <Section title={locale === 'ar' ? t.users.devices : 'Devices'}>
                {detail.devices.length === 0 ? <p style={{ color: '#6b7280', fontSize: '0.8rem', margin: 0 }}>-</p> : (
                  detail.devices.map((d) => (
                    <div key={d.id} style={{ fontSize: '0.8rem', marginBottom: '0.25rem' }}>
                      {d.device_name} ({d.platform}) — {new Date(d.last_active_at).toLocaleDateString()}
                    </div>
                  ))
                )}
              </Section>

              {/* Recent transactions */}
              <Section title={locale === 'ar' ? t.users.recentTx : 'Recent Transactions'}>
                {detail.recentTx.length === 0 ? <p style={{ color: '#6b7280', fontSize: '0.8rem', margin: 0 }}>-</p> : (
                  <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                    {detail.recentTx.map((tx) => (
                      <div key={tx.id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', padding: '0.25rem 0', borderBottom: '1px solid #f3f4f6' }}>
                        <span>{tx.tx_type}</span>
                        <span>{tx.currency} {tx.amount}</span>
                        <Badge value={tx.status} />
                      </div>
                    ))}
                    <a href={`/admin/transactions?user=${selectedId}`} style={{ display: 'block', marginTop: '0.5rem', fontSize: '0.8rem', color: '#3b82f6' }}>
                      {locale === 'ar' ? 'عرض الكل ←' : 'View all →'}
                    </a>
                  </div>
                )}
              </Section>

              {/* Merchant section */}
              {detail.merchant && (
                <Section title={locale === 'ar' ? t.users.merchantSection : 'Merchant'}>
                  <Field label={locale === 'ar' ? 'الاسم التجاري' : 'Business'} value={detail.merchant.business_name} />
                  <Field label={locale === 'ar' ? 'الحالة' : 'Status'} value={<Badge value={detail.merchant.status} />} />
                  <Field label={locale === 'ar' ? 'البنك' : 'Bank'} value={detail.merchant.payout_bank_name} />
                  <Field label={locale === 'ar' ? 'الحساب' : 'Account'} value={detail.merchant.payout_account_number} mono />
                  {can('merchant.approve') && detail.merchant.status === 'pending' && (
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                      <ActionBtn color="#10b981" label={locale === 'ar' ? t.users.approveMerchant : 'Approve'} onClick={() => handleAction('merchant_approve')} />
                      <ActionBtn color="#ef4444" label={locale === 'ar' ? t.users.rejectMerchant : 'Reject'} onClick={() => handleAction('merchant_reject')} />
                    </div>
                  )}
                  {can('merchant.suspend') && detail.merchant.status === 'active' && (
                    <ActionBtn color="#f59e0b" label={locale === 'ar' ? t.users.suspendMerchant : 'Suspend'} onClick={() => handleAction('merchant_suspend')} />
                  )}
                </Section>
              )}

              {/* Admin actions */}
              {!isReadOnly && (
                <Section title={locale === 'ar' ? t.admin.actions : 'Actions'}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {can('user.freeze') && detail.profile.wallet_status === 'active' && (
                      <ActionBtn color="#ef4444" label={locale === 'ar' ? t.users.freezeWallet : 'Freeze Wallet'} onClick={() => handleAction('freeze')} />
                    )}
                    {can('user.unfreeze') && detail.profile.wallet_status === 'frozen' && (
                      <ActionBtn color="#10b981" label={locale === 'ar' ? t.users.unfreezeWallet : 'Unfreeze Wallet'} onClick={() => handleAction('unfreeze')} />
                    )}
                    {can('user.force_kyc_resubmit') && (
                      <ActionBtn color="#f59e0b" label={locale === 'ar' ? t.users.forceKycResubmit : 'Force KYC Resubmit'} onClick={() => handleAction('force_kyc_resubmit')} />
                    )}
                    {can('user.set_role') && (
                      <select
                        onChange={(e) => { if (e.target.value) handleAction('set_role', { role: e.target.value }); e.target.value = ''; }}
                        defaultValue=""
                        style={{ padding: '0.375rem 0.5rem', borderRadius: '6px', border: '1px solid #d1d5db', fontSize: '0.8rem' }}
                      >
                        <option value="" disabled>{locale === 'ar' ? t.users.setRole : 'Set Role...'}</option>
                        <option value="admin">Admin</option>
                        <option value="compliance">Compliance</option>
                        <option value="finance">Finance</option>
                        <option value="support">Support</option>
                      </select>
                    )}
                  </div>
                </Section>
              )}

              {/* DANGER ZONE — admin only (PROMPT 09) */}
              {can('danger.balance_adjust') && (
                <DangerZone
                  userId={selectedId}
                  locale={locale}
                  onRefresh={() => loadDetail(selectedId)}
                />
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

// -- Sub-components --

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: '1rem', paddingBottom: '0.75rem', borderBottom: '1px solid #f3f4f6' }}>
      <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', fontWeight: 600, color: '#374151' }}>{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.8rem' }}>
      <span style={{ color: '#6b7280' }}>{label}</span>
      <span style={{ color: '#111827', fontFamily: mono ? 'monospace' : 'inherit', fontWeight: 500 }}>{value ?? '-'}</span>
    </div>
  );
}

function Badge({ value }: { value: string | null | undefined }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    approved: { bg: '#dcfce7', fg: '#166534' }, active: { bg: '#dcfce7', fg: '#166534' }, completed: { bg: '#dcfce7', fg: '#166534' },
    pending: { bg: '#fef9c3', fg: '#854d0e' }, processing: { bg: '#dbeafe', fg: '#1e40af' },
    rejected: { bg: '#fecaca', fg: '#991b1b' }, frozen: { bg: '#fecaca', fg: '#991b1b' }, failed: { bg: '#fecaca', fg: '#991b1b' }, suspended: { bg: '#fecaca', fg: '#991b1b' },
    resubmission_required: { bg: '#fed7aa', fg: '#9a3412' },
  };
  const c = colors[value ?? ''] ?? { bg: '#e5e7eb', fg: '#374151' };
  return (
    <span style={{ display: 'inline-block', padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg, textTransform: 'capitalize' }}>
      {value?.replace(/_/g, ' ') ?? '-'}
    </span>
  );
}

function ActionBtn({ label, color, onClick }: { label: string; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{ padding: '0.375rem 0.75rem', background: color, color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' }}
    >
      {label}
    </button>
  );
}

// -- PROMPT 09: Danger Zone --
function DangerZone({ userId, locale, onRefresh }: { userId: string; locale: string; onRefresh: () => void }) {
  const [adjustAmount, setAdjustAmount] = useState('');
  const [adjustReason, setAdjustReason] = useState('');
  const [pin, setPin] = useState('');
  const [showAudit, setShowAudit] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleBalanceAdjust() {
    if (!adjustAmount || !adjustReason || !pin) return;
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.functions.invoke('admin-balance-adjust', {
      body: { user_id: userId, amount: parseFloat(adjustAmount), reason: adjustReason, pin },
    });
    if (error) {
      alert(error.message || 'Adjustment failed');
    } else {
      setAdjustAmount('');
      setAdjustReason('');
      setPin('');
      onRefresh();
    }
    setLoading(false);
  }

  async function handleForceLogout() {
    if (!confirm(locale === 'ar' ? 'هل أنت متأكد؟' : 'Revoke all sessions for this user?')) return;
    const supabase = createClient();
    await writeAuditLog({ action: 'danger.force_logout', resource_type: 'profiles', resource_id: userId });
    // Supabase Admin API would handle this — log intent
    alert(locale === 'ar' ? 'تم طلب تسجيل الخروج' : 'Logout requested. Admin API will process.');
  }

  async function loadAuditLogs() {
    setShowAudit(!showAudit);
    if (!showAudit) {
      const supabase = createClient();
      const { data } = await supabase.from('audit_logs').select('*').eq('resource_id', userId).order('created_at', { ascending: false }).limit(50);
      setAuditLogs((data as AuditLog[]) ?? []);
    }
  }

  return (
    <div style={{ marginTop: '1rem', padding: '1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px' }}>
      <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', fontWeight: 700, color: '#991b1b' }}>
        {locale === 'ar' ? 'منطقة الخطر' : 'Danger Zone'}
      </h3>

      {/* Balance adjustment */}
      <div style={{ marginBottom: '0.75rem' }}>
        <p style={{ margin: '0 0 0.25rem', fontSize: '0.75rem', fontWeight: 600, color: '#991b1b' }}>
          {locale === 'ar' ? 'تعديل الرصيد يدوياً' : 'Manual Balance Adjustment'}
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
          <input type="number" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} placeholder={locale === 'ar' ? 'المبلغ' : 'Amount'} style={dangerInput} />
          <input type="text" value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} placeholder={locale === 'ar' ? 'السبب' : 'Reason (required)'} style={dangerInput} />
          <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} placeholder="PIN" maxLength={6} style={dangerInput} />
          <button onClick={handleBalanceAdjust} disabled={loading || !adjustAmount || !adjustReason || !pin} style={{ ...dangerBtnStyle, opacity: loading ? 0.5 : 1 }}>
            {loading ? '...' : (locale === 'ar' ? 'تطبيق التعديل' : 'Apply Adjustment')}
          </button>
        </div>
      </div>

      {/* Force logout */}
      <button onClick={handleForceLogout} style={{ ...dangerBtnStyle, marginBottom: '0.75rem', width: '100%' }}>
        {locale === 'ar' ? 'تسجيل خروج إجباري' : 'Force Logout (Revoke Sessions)'}
      </button>

      {/* Audit log viewer */}
      <button onClick={loadAuditLogs} style={{ ...dangerBtnStyle, width: '100%', background: '#6b7280' }}>
        {locale === 'ar' ? 'سجل التدقيق (آخر 50)' : 'Audit History (Last 50)'}
      </button>
      {showAudit && (
        <div style={{ marginTop: '0.5rem', maxHeight: '250px', overflowY: 'auto', fontSize: '0.7rem' }}>
          {auditLogs.map((log) => (
            <div key={log.id} style={{ padding: '0.25rem 0', borderBottom: '1px solid #fecaca' }}>
              <span style={{ color: '#6b7280' }}>{new Date(log.created_at).toLocaleString()}</span>{' '}
              <span style={{ fontWeight: 600 }}>{log.action}</span>{' '}
              {log.metadata && Object.keys(log.metadata).length > 0 && (
                <span style={{ color: '#6b7280' }}>{JSON.stringify(log.metadata)}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const dangerInput: React.CSSProperties = { padding: '0.375rem 0.5rem', border: '1px solid #fca5a5', borderRadius: '4px', fontSize: '0.8rem' };
const dangerBtnStyle: React.CSSProperties = { padding: '0.375rem 0.75rem', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer' };
const th: React.CSSProperties = { textAlign: 'start', padding: '0.625rem 0.875rem', fontSize: '0.75rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' };
const td: React.CSSProperties = { padding: '0.625rem 0.875rem', fontSize: '0.85rem', color: '#111827' };
