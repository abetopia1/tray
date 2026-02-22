'use client';

import { useState, useEffect, useCallback } from 'react';
import { createClient } from '@/lib/supabase/client';
import { useI18n } from '@/lib/i18n/context';
import { useAdmin } from '../context';
import { writeAuditLog } from '@/lib/audit';
import type { SupportTicket, SupportMessage, TicketStatus } from '@/types/database';

const STATUS_OPTIONS: TicketStatus[] = ['open', 'in_progress', 'resolved', 'closed'];

export default function SupportPage() {
  const { t, locale } = useI18n();
  const { can, userId: actorId, roles } = useAdmin();
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null);

  // Thread
  const [messages, setMessages] = useState<SupportMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [threadLoading, setThreadLoading] = useState(false);

  const fetchTickets = useCallback(async () => {
    setLoading(true);
    const supabase = createClient();
    let query = supabase.from('support_tickets').select('*, profiles!support_tickets_user_id_fkey(full_name, phone_e164)').order('created_at', { ascending: sortOrder === 'oldest' }).limit(100);
    if (statusFilter) query = query.eq('status', statusFilter);
    const { data } = await query;
    const mapped = ((data ?? []) as (SupportTicket & { profiles?: { full_name?: string; phone_e164?: string } })[]).map((t) => ({
      ...t,
      user_name: t.profiles?.full_name ?? undefined,
      user_phone: t.profiles?.phone_e164 ?? undefined,
    }));
    setTickets(mapped);
    setLoading(false);
  }, [statusFilter, sortOrder]);

  useEffect(() => { fetchTickets(); }, [fetchTickets]);

  const loadThread = useCallback(async (ticket: SupportTicket) => {
    setSelectedTicket(ticket);
    setThreadLoading(true);
    const supabase = createClient();
    const { data } = await supabase.from('support_ticket_messages').select('*').eq('ticket_id', ticket.id).order('created_at', { ascending: true });
    setMessages((data as SupportMessage[]) ?? []);
    setThreadLoading(false);
  }, []);

  async function handleSendMessage() {
    if (!newMessage.trim() || !selectedTicket) return;
    setSending(true);
    const supabase = createClient();
    const authorRole = roles.includes('admin') ? 'admin' : 'support';
    await supabase.from('support_ticket_messages').insert({
      ticket_id: selectedTicket.id,
      author_id: actorId,
      author_role: authorRole,
      body: newMessage.trim(),
    });
    // Update ticket to in_progress if it was open
    if (selectedTicket.status === 'open') {
      await supabase.from('support_tickets').update({ status: 'in_progress', assigned_to: actorId }).eq('id', selectedTicket.id);
    }
    await writeAuditLog({ action: 'support.respond', resource_type: 'support_tickets', resource_id: selectedTicket.id });
    setNewMessage('');
    setSending(false);
    loadThread(selectedTicket);
    fetchTickets();
  }

  async function handleStatusChange(newStatus: TicketStatus) {
    if (!selectedTicket) return;
    const supabase = createClient();
    await supabase.from('support_tickets').update({ status: newStatus }).eq('id', selectedTicket.id);
    await writeAuditLog({ action: `support.${newStatus}`, resource_type: 'support_tickets', resource_id: selectedTicket.id });
    setSelectedTicket({ ...selectedTicket, status: newStatus });
    fetchTickets();
  }

  return (
    <div style={{ display: 'flex', gap: '1.5rem', minHeight: 'calc(100vh - 4rem)' }}>
      {/* Ticket list */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1 style={{ margin: '0 0 1rem', fontSize: '1.25rem', fontWeight: 700 }}>
          {locale === 'ar' ? t.support.title : 'Support Tickets'}
        </h1>

        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          {STATUS_OPTIONS.map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)} style={filterBtn(statusFilter === s)}>{s.replace(/_/g, ' ')}</button>
          ))}
          <button onClick={() => setStatusFilter('')} style={filterBtn(statusFilter === '')}>{locale === 'ar' ? t.admin.all : 'All'}</button>
          <span style={{ borderInlineStart: '1px solid #d1d5db', height: '24px', margin: '0 0.25rem' }} />
          <button onClick={() => setSortOrder(sortOrder === 'newest' ? 'oldest' : 'newest')} style={{ padding: '0.375rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', background: '#fff', fontSize: '0.8rem', cursor: 'pointer' }}>
            {sortOrder === 'newest' ? (locale === 'ar' ? t.support.newest : 'Newest') : (locale === 'ar' ? t.support.oldest : 'Oldest')}
          </button>
        </div>

        {loading ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
        ) : tickets.length === 0 ? (
          <p style={{ color: '#6b7280' }}>{locale === 'ar' ? t.admin.noResults : 'No tickets found'}</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {tickets.map((ticket) => (
              <div key={ticket.id} onClick={() => loadThread(ticket)} style={{
                background: selectedTicket?.id === ticket.id ? '#eff6ff' : '#fff',
                borderRadius: '8px', padding: '0.75rem 1rem', cursor: 'pointer',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                borderInlineStart: `4px solid ${ticket.status === 'open' ? '#ef4444' : ticket.status === 'in_progress' ? '#f59e0b' : '#10b981'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{ticket.subject}</span>
                  <Badge value={ticket.status} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#6b7280' }}>
                  <span>{ticket.user_name || ticket.user_phone || '-'}</span>
                  <span>{new Date(ticket.created_at).toLocaleDateString()}</span>
                </div>
                {ticket.category && <span style={{ fontSize: '0.65rem', color: '#6b7280', background: '#f3f4f6', padding: '0.125rem 0.375rem', borderRadius: '4px', marginTop: '0.25rem', display: 'inline-block' }}>{ticket.category}</span>}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ticket detail / thread */}
      {selectedTicket && (
        <div style={{ width: '420px', flexShrink: 0, background: '#fff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 4rem)' }}>
          {/* Header */}
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid #e5e7eb' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>{selectedTicket.subject}</h2>
              <button onClick={() => setSelectedTicket(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: '#6b7280' }}>{'\u2715'}</button>
            </div>
            {/* User info summary */}
            <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: '#6b7280' }}>
              <span>{locale === 'ar' ? t.support.userInfo : 'User'}: {selectedTicket.user_name || '-'} | {selectedTicket.user_phone || '-'}</span>
            </div>
            {/* Status actions */}
            <div style={{ display: 'flex', gap: '0.375rem', marginTop: '0.5rem' }}>
              {can('support.close') && selectedTicket.status !== 'closed' && (
                <button onClick={() => handleStatusChange('closed')} style={smallBtn('#6b7280')}>
                  {locale === 'ar' ? t.support.closeTicket : 'Close'}
                </button>
              )}
              {can('support.reopen') && selectedTicket.status === 'closed' && (
                <button onClick={() => handleStatusChange('open')} style={smallBtn('#3b82f6')}>
                  {locale === 'ar' ? t.support.reopenTicket : 'Reopen'}
                </button>
              )}
            </div>
          </div>

          {/* Messages thread */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '1rem 1.25rem' }}>
            {selectedTicket.description && (
              <div style={{ marginBottom: '0.75rem', padding: '0.5rem 0.75rem', background: '#f9fafb', borderRadius: '6px', fontSize: '0.85rem' }}>
                {selectedTicket.description}
              </div>
            )}
            {threadLoading ? (
              <p style={{ color: '#6b7280', fontSize: '0.8rem' }}>{locale === 'ar' ? t.admin.loading : 'Loading...'}</p>
            ) : messages.length === 0 ? (
              <p style={{ color: '#6b7280', fontSize: '0.8rem' }}>{locale === 'ar' ? 'لا توجد رسائل بعد' : 'No messages yet'}</p>
            ) : (
              messages.map((msg) => {
                const isStaff = msg.author_role !== 'user';
                return (
                  <div key={msg.id} style={{ marginBottom: '0.5rem', display: 'flex', justifyContent: isStaff ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '80%', padding: '0.5rem 0.75rem', borderRadius: '8px',
                      background: isStaff ? '#eff6ff' : '#f3f4f6',
                      borderBottomLeftRadius: isStaff ? '8px' : '2px',
                      borderBottomRightRadius: isStaff ? '2px' : '8px',
                    }}>
                      <p style={{ margin: 0, fontSize: '0.85rem' }}>{msg.body}</p>
                      <p style={{ margin: '0.25rem 0 0', fontSize: '0.65rem', color: '#9ca3af' }}>
                        {msg.author_role} — {new Date(msg.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Compose */}
          {can('support.respond') && selectedTicket.status !== 'closed' && (
            <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid #e5e7eb', display: 'flex', gap: '0.5rem' }}>
              <input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder={locale === 'ar' ? 'اكتب رداً...' : 'Type a response...'}
                style={{ flex: 1, padding: '0.5rem 0.75rem', border: '1px solid #d1d5db', borderRadius: '6px', fontSize: '0.85rem' }}
              />
              <button onClick={handleSendMessage} disabled={sending || !newMessage.trim()} style={{
                padding: '0.5rem 1rem', background: '#111827', color: '#fff', border: 'none', borderRadius: '6px', fontSize: '0.85rem', cursor: 'pointer',
              }}>
                {sending ? '...' : (locale === 'ar' ? 'إرسال' : 'Send')}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Badge({ value }: { value: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    open: { bg: '#fecaca', fg: '#991b1b' }, in_progress: { bg: '#fef9c3', fg: '#854d0e' },
    resolved: { bg: '#dcfce7', fg: '#166534' }, closed: { bg: '#e5e7eb', fg: '#374151' },
  };
  const c = colors[value] ?? { bg: '#e5e7eb', fg: '#374151' };
  return <span style={{ padding: '0.125rem 0.5rem', borderRadius: '9999px', fontSize: '0.7rem', fontWeight: 600, background: c.bg, color: c.fg }}>{value.replace(/_/g, ' ')}</span>;
}

function filterBtn(active: boolean): React.CSSProperties {
  return {
    padding: '0.375rem 0.75rem', borderRadius: '6px', fontSize: '0.8rem', cursor: 'pointer',
    border: active ? '2px solid #3b82f6' : '1px solid #d1d5db',
    background: active ? '#eff6ff' : '#fff', color: active ? '#1d4ed8' : '#374151',
    fontWeight: active ? 600 : 400, textTransform: 'capitalize' as const,
  };
}

function smallBtn(bg: string): React.CSSProperties {
  return { padding: '0.25rem 0.5rem', background: bg, color: '#fff', border: 'none', borderRadius: '4px', fontSize: '0.7rem', cursor: 'pointer' };
}
