export type AdminRole = 'admin' | 'compliance' | 'finance' | 'support';

export type TxType = 'p2p' | 'merchant_payment' | 'refund' | 'deposit' | 'withdrawal' | 'adjustment';
export type TxStatus = 'pending' | 'completed' | 'failed' | 'reversed';
export type KycStatus = 'pending' | 'approved' | 'rejected' | 'resubmission_required';
export type MerchantStatus = 'pending' | 'active' | 'suspended' | 'rejected';
export type WalletStatus = 'active' | 'frozen';
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed';
export type BatchStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type ReconStatus = 'open' | 'investigating' | 'resolved';
export type PayoutItemStatus = 'pending' | 'confirmed' | 'failed';

export interface Profile {
  id: string;
  phone_e164: string | null;
  handle: string | null;
  full_name: string | null;
  kyc_status: KycStatus;
  wallet_status: WalletStatus;
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

export interface Device {
  id: string;
  user_id: string;
  device_name: string;
  platform: string;
  last_active_at: string;
  created_at: string;
}

export interface MerchantProfile {
  id: string;
  user_id: string;
  business_name: string;
  status: MerchantStatus;
  payout_bank_name: string | null;
  payout_account_number: string | null;
  payout_routing_number: string | null;
  created_at: string;
  updated_at: string;
}

export interface Merchant {
  id: string;
  name: string;
  status: MerchantStatus;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Transaction {
  id: string;
  merchant_id: string | null;
  sender_id: string | null;
  receiver_id: string | null;
  tx_type: TxType;
  amount: number;
  fee: number;
  currency: string;
  status: TxStatus;
  reference_tx_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface KycReview {
  id: string;
  user_id: string;
  full_name: string | null;
  national_id: string | null;
  dob: string | null;
  selfie_path: string | null;
  status: KycStatus;
  reason_code: string | null;
  reviewer_id: string | null;
  notes: string | null;
  submitted_at: string;
  created_at: string;
  updated_at: string;
}

export interface SettlementBatch {
  id: string;
  run_date: string;
  cutoff_at: string;
  gross_amount: number;
  total_fees: number;
  net_amount: number;
  item_count: number;
  currency: string;
  status: BatchStatus;
  export_url: string | null;
  created_at: string;
  settled_at: string | null;
}

export interface PayoutItem {
  id: string;
  batch_id: string;
  merchant_id: string;
  amount: number;
  reference: string;
  status: PayoutItemStatus;
  created_at: string;
}

export interface ReconciliationException {
  id: string;
  batch_id: string | null;
  transaction_id: string | null;
  payout_item_id: string | null;
  reason: string;
  status: ReconStatus;
  resolution_notes: string | null;
  resolved_by: string | null;
  created_at: string;
  resolved_at: string | null;
}

export interface SupportTicket {
  id: string;
  user_id: string | null;
  subject: string;
  description: string | null;
  category: string | null;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: TicketStatus;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
  // Joined fields
  user_name?: string;
  user_phone?: string;
}

export interface SupportMessage {
  id: string;
  ticket_id: string;
  author_id: string;
  author_role: 'user' | 'support' | 'admin';
  body: string;
  created_at: string;
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

export interface AppConfig {
  key: string;
  value: string;
}

// Dashboard aggregates
export interface AdminKpis {
  total_users: number;
  total_merchants: number;
  today_volume: number;
  today_fees: number;
  failed_tx_count: number;
  new_users_today: number;
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
  kyc_status: string | null;
  wallet_status: string | null;
}

// User detail (joined view for admin/users page)
export interface UserDetail extends Profile {
  roles: AdminRole[];
  merchant_profile: MerchantProfile | null;
  devices: Device[];
  recent_transactions: Transaction[];
  kyc_review: KycReview | null;
}
