'use client';

import { useState, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { SearchResult } from '@/types/database';

export default function GlobalSearch() {
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
      const { data, error } = await supabase.functions.invoke('admin-search', {
        body: { query: trimmed },
      });

      if (error) throw error;
      setResults((data?.results as SearchResult[]) ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      handleSearch();
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search users by phone, handle, or name..."
          style={{
            flex: 1,
            padding: '0.625rem 0.875rem',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '0.9rem',
            outline: 'none',
          }}
        />
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          style={{
            padding: '0.625rem 1.25rem',
            background: loading ? '#9ca3af' : '#111827',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.9rem',
            cursor: loading ? 'not-allowed' : 'pointer',
            whiteSpace: 'nowrap',
          }}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {searched && (
        <div style={{ marginTop: '0.75rem' }}>
          {results.length === 0 ? (
            <p style={{ color: '#6b7280', fontSize: '0.875rem', margin: 0 }}>
              No users found matching &quot;{query}&quot;
            </p>
          ) : (
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              background: '#fff',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  <th style={thStyle}>Name</th>
                  <th style={thStyle}>Handle</th>
                  <th style={thStyle}>Phone</th>
                  <th style={thStyle}>ID</th>
                </tr>
              </thead>
              <tbody>
                {results.map((user) => (
                  <tr key={user.id} style={{ borderTop: '1px solid #e5e7eb' }}>
                    <td style={tdStyle}>{user.full_name || '-'}</td>
                    <td style={tdStyle}>{user.handle || '-'}</td>
                    <td style={tdStyle}>{user.phone_e164 || '-'}</td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: '0.75rem', color: '#6b7280' }}>
                      {user.id.slice(0, 8)}...
                    </td>
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

const thStyle: React.CSSProperties = {
  textAlign: 'left',
  padding: '0.625rem 0.875rem',
  fontSize: '0.75rem',
  fontWeight: 600,
  color: '#6b7280',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
};

const tdStyle: React.CSSProperties = {
  padding: '0.625rem 0.875rem',
  fontSize: '0.875rem',
  color: '#111827',
};
