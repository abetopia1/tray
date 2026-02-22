export type AdminRole = 'admin' | 'compliance' | 'finance' | 'support';

export interface Profile {
  id: string;
  phone_e164: string | null;
  handle: string | null;
  full_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserRole {
  id: string;
  user_id: string;
  role: AdminRole;
  granted_by: string | null;
  created_at: string;
}

export interface Merchant {
  id: string;
  name: string;
  status: 'pending' | 'active' | 'suspended' | 'rejected';
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  merchant_id: string;
  amount: number;
  fee: number;
  currency: string;
  status: 'pending' | 'completed' | 'failed' | 'reversed';
  created_at: string;
}

export interface KycReview {
  id: string;
  user_id: string;
  status: 'pending' | 'approved' | 'rejected';
  reviewer_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface SettlementBatch {
  id: string;
  merchant_id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  settled_at: string | null;
}

export interface ReconciliationException {
  id: string;
  transaction_id: string | null;
  reason: string;
  status: 'open' | 'investigating' | 'resolved';
  resolved_by: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface SupportTicket {
  id: string;
  user_id: string | null;
  subject: string;
  description: string | null;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface AdminKpis {
  total_users: number;
  total_merchants: number;
  today_volume: number;
  today_fees: number;
  failed_tx_count: number;
}

export interface QueueCounts {
  kyc_pending: number;
  merchant_pending: number;
  settlement_batches: number;
  reconciliation_exceptions: number;
  support_tickets: number;
}

export interface SearchResult {
  id: string;
  phone_e164: string | null;
  handle: string | null;
  full_name: string | null;
}
