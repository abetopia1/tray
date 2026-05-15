'use client';

import { useCallback, useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';
import type { HermesJob, HermesJobStatus } from '@/types/database';

type ListResponse = {
  jobs: HermesJob[];
  summary: Partial<Record<HermesJobStatus, number>>;
};

const STATUS_COLORS: Record<HermesJobStatus, string> = {
  pending: '#6b7280',
  running: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#9ca3af',
};

export default function HermesJobsPage() {
  const [jobs, setJobs] = useState<HermesJob[]>([]);
  const [summary, setSummary] = useState<ListResponse['summary']>({});
  const [statusFilter, setStatusFilter] = useState<HermesJobStatus | ''>('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { data, error } = await supabase.functions.invoke<ListResponse>('admin-jobs-list', {
        body: { status: statusFilter || undefined, limit: 100 },
      });
      if (error) throw error;
      setJobs(data?.jobs ?? []);
      setSummary(data?.summary ?? {});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const enqueueTest = async () => {
    setBusy('enqueue');
    setError(null);
    try {
      const supabase = createClient();
      const { error } = await supabase.functions.invoke('admin-jobs-enqueue', {
        body: { type: 'noop', payload: { ts: new Date().toISOString() } },
      });
      if (error) throw error;
      await fetchJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to enqueue');
    } finally {
      setBusy(null);
    }
  };

  const retryJob = async (id: string) => {
    setBusy(id);
    setError(null);
    try {
      const supabase = createClient();
      const { error } = await supabase.functions.invoke('admin-jobs-retry', { body: { id } });
      if (error) throw error;
      await fetchJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to retry');
    } finally {
      setBusy(null);
    }
  };

  const STATUSES: HermesJobStatus[] = ['pending', 'running', 'completed', 'failed', 'cancelled'];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, color: '#111827' }}>Hermes Jobs</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            onClick={enqueueTest}
            disabled={busy === 'enqueue'}
            style={{ padding: '0.5rem 1rem', background: '#111827', color: '#fff', border: 'none', borderRadius: 6, fontSize: '0.85rem', cursor: 'pointer', opacity: busy === 'enqueue' ? 0.6 : 1 }}
          >
            {busy === 'enqueue' ? 'Enqueuing…' : 'Enqueue test job'}
          </button>
          <button
            onClick={fetchJobs}
            style={{ padding: '0.5rem 1rem', background: '#fff', border: '1px solid #d1d5db', borderRadius: 6, fontSize: '0.85rem', cursor: 'pointer' }}
          >
            Refresh
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem', marginBottom: '1rem' }}>
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(statusFilter === s ? '' : s)}
            style={{
              padding: '0.6rem', borderRadius: 8, border: '1px solid #e5e7eb',
              background: statusFilter === s ? '#f3f4f6' : '#fff', cursor: 'pointer', textAlign: 'left',
            }}
          >
            <div style={{ fontSize: '0.7rem', color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s}</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: STATUS_COLORS[s] }}>{summary[s] ?? 0}</div>
          </button>
        ))}
      </div>

      {error && (
        <div style={{ padding: '0.75rem 1rem', background: '#fef2f2', color: '#991b1b', borderRadius: 6, marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 1px 3px rgba(0,0,0,0.08)', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ background: '#f9fafb', textAlign: 'start' }}>
              <th style={th}>Type</th>
              <th style={th}>Status</th>
              <th style={th}>Attempts</th>
              <th style={th}>Run at</th>
              <th style={th}>Last error</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} style={{ padding: '1.5rem', textAlign: 'center', color: '#6b7280' }}>Loading…</td></tr>
            )}
            {!loading && jobs.length === 0 && (
              <tr><td colSpan={6} style={{ padding: '1.5rem', textAlign: 'center', color: '#6b7280' }}>No jobs</td></tr>
            )}
            {jobs.map((job) => (
              <tr key={job.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                <td style={td}><code>{job.type}</code></td>
                <td style={td}>
                  <span style={{ display: 'inline-block', padding: '0.15rem 0.5rem', borderRadius: 4, background: STATUS_COLORS[job.status] + '20', color: STATUS_COLORS[job.status], fontWeight: 600, fontSize: '0.75rem' }}>
                    {job.status}
                  </span>
                </td>
                <td style={td}>{job.attempts} / {job.max_attempts}</td>
                <td style={td}>{new Date(job.run_at).toLocaleString()}</td>
                <td style={{ ...td, maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#991b1b' }} title={job.last_error ?? ''}>
                  {job.last_error ?? '—'}
                </td>
                <td style={td}>
                  {job.status === 'failed' && (
                    <button
                      onClick={() => retryJob(job.id)}
                      disabled={busy === job.id}
                      style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', background: '#fff', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer' }}
                    >
                      {busy === job.id ? '…' : 'Retry'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const th: React.CSSProperties = { padding: '0.6rem 0.75rem', fontWeight: 600, color: '#374151', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'start' };
const td: React.CSSProperties = { padding: '0.6rem 0.75rem', color: '#111827', verticalAlign: 'top' };
