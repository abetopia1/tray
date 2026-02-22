'use client';

import { useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import type { SearchResult } from '@/types/database';

export default function GlobalSearch() {
  const { t, locale } = useI18n();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setLoading(true);
    setSearched(true);
    try {
      const supabase = createClient();
      const { data, error } = await supabase.functions.invoke('admin-search', { body: { query: trimmed } });
      if (error) throw error;
      setResults((data?.results as SearchResult[]) ?? []);
    } catch { setResults([]); } finally { setLoading(false); }
  }, [query]);

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder={locale === 'ar' ? t.users.searchPlaceholder : 'Search by phone, handle, or name...'}
          style={{ flex: 1, padding: '0.625rem 0.875rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.9rem', outline: 'none' }}
        />
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          style={{
            padding: '0.625rem 1.25rem', background: loading ? '#9ca3af' : '#111827',
            color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.9rem',
            cursor: loading ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
          }}
        >
          {loading ? (locale === 'ar' ? 'جارٍ البحث...' : 'Searching...') : (locale === 'ar' ? t.admin.search : 'Search')}
        </button>
      </div>
      {searched && (
        <div style={{ marginTop: '0.75rem' }}>
          {results.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: '0.875rem', margin: 0 }}>{locale === 'ar' ? t.admin.noResults : 'No results found'}</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={thStyle}>{locale === 'ar' ? 'الاسم' : 'Name'}</th>
                  <th style={thStyle}>{locale === 'ar' ? 'المعرف' : 'Handle'}</th>
                  <th style={thStyle}>{locale === 'ar' ? 'الهاتف' : 'Phone'}</th>
                  <th style={thStyle}>KYC</th>
                  <th style={thStyle}>{locale === 'ar' ? 'المحفظة' : 'Wallet'}</th>
                </tr>
              </thead>
              <tbody>
                {results.map((user) => (
                  <tr key={user.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                    <td style={tdStyle}>
                      <a href={`/admin/users?selected=${user.id}`} style={{ color: '#3b82f6', textDecoration: 'none' }}>
                        {user.full_name || '-'}
                      </a>
                    </td>
                    <td style={tdStyle}>{user.handle || '-'}</td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '0.8rem' }}>{user.phone_e164 || '-'}</td>
                    <td style={tdStyle}><StatusBadge value={user.kyc_status} /></td>
                    <td style={tdStyle}><StatusBadge value={user.wallet_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ value }: { value: string | null }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    approved: { bg: '#dcfce7', fg: '#166534' }, active: { bg: '#dcfce7', fg: '#166534' },
    pending: { bg: '#fef9c3', fg: '#854d0e' }, rejected: { bg: '#fecaca', fg: '#991b1b' },
    frozen: { bg: '#fecaca', fg: '#991b1b' }, resubmission_required: { bg: '#fed7aa', fg: '#9a3412' },
  };
  const c = colors[value ?? ''] ?? { bg: '#e5e7eb', fg: '#374151' };
  return (
    <span style={{ display: 'inline-block', padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg, textTransform: 'capitalize' }}>
      {value?.replace(/_/g, ' ') ?? '-'}
    </span>
  );
}

const thStyle: React.CSSProperties = { textAlign: 'start', padding: '0.625rem 0.875rem', fontSize: '0.75rem', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' };
const tdStyle: React.CSSProperties = { padding: '0.625rem 0.875rem', fontSize: '0.875rem', color: '#111827' };
