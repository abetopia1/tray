export type TxType = 'p2p' | 'merchant_payment' | 'refund' | 'deposit' | 'withdrawal' | 'adjustment';
export type TxStatus = 'pending' | 'completed' | 'failed' | 'reversed';
export type KycStatus = 'pending' | 'approved' | 'rejected' | 'resubmission_required';
export type MerchantStatus = 'pending' | 'active' | 'suspended' | 'rejected';
export type WalletStatus = 'active' | 'frozen';
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed';

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
}

export interface SupportMessage {
  id: string;
  ticket_id: string;
  author_id: string;
  author_role: 'user' | 'support' | 'admin';
  body: string;
  created_at: string;
}

export interface AppConfig {
  key: string;
  value: string;
}
