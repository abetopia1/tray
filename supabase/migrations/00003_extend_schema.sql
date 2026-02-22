-- ============================================================
-- Extended schema for full admin back-office
-- ============================================================

-- Enable trigram extension for fuzzy search (if not already)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Add kyc_status and wallet_status to profiles
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS kyc_status TEXT NOT NULL DEFAULT 'pending'
  CHECK (kyc_status IN ('pending', 'approved', 'rejected', 'resubmission_required'));
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS wallet_status TEXT NOT NULL DEFAULT 'active'
  CHECK (wallet_status IN ('active', 'frozen'));

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  device_name     TEXT NOT NULL,
  platform        TEXT NOT NULL DEFAULT 'unknown',
  push_token      TEXT,
  last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_devices_user ON devices (user_id);

-- Merchant profiles (per-user merchant data, linked to profiles)
CREATE TABLE IF NOT EXISTS merchant_profiles (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  business_name         TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'active', 'suspended', 'rejected')),
  payout_bank_name      TEXT,
  payout_account_number TEXT,
  payout_routing_number TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_merchant_profiles_status ON merchant_profiles (status);
CREATE INDEX IF NOT EXISTS idx_merchant_profiles_user ON merchant_profiles (user_id);

-- Extend transactions table
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS sender_id UUID REFERENCES auth.users(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS receiver_id UUID REFERENCES auth.users(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS tx_type TEXT NOT NULL DEFAULT 'merchant_payment'
  CHECK (tx_type IN ('p2p', 'merchant_payment', 'refund', 'deposit', 'withdrawal', 'adjustment'));
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reference_tx_id UUID REFERENCES transactions(id);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
-- Make merchant_id nullable for non-merchant transactions
ALTER TABLE transactions ALTER COLUMN merchant_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions (sender_id);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions (receiver_id);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions (tx_type);

-- Extend kyc_reviews with identity fields
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS full_name TEXT;
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS national_id TEXT;
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS dob DATE;
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS selfie_path TEXT;
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS reason_code TEXT;
ALTER TABLE kyc_reviews ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ NOT NULL DEFAULT now();
-- Expand status to include resubmission_required
ALTER TABLE kyc_reviews DROP CONSTRAINT IF EXISTS kyc_reviews_status_check;
ALTER TABLE kyc_reviews ADD CONSTRAINT kyc_reviews_status_check
  CHECK (status IN ('pending', 'approved', 'rejected', 'resubmission_required'));

-- Extend settlement_batches for full batch model
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS run_date DATE NOT NULL DEFAULT CURRENT_DATE;
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS cutoff_at TIMESTAMPTZ NOT NULL DEFAULT now();
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS gross_amount NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS total_fees NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS net_amount NUMERIC(18,2) NOT NULL DEFAULT 0;
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS item_count INT NOT NULL DEFAULT 0;
ALTER TABLE settlement_batches ADD COLUMN IF NOT EXISTS export_url TEXT;
-- Make merchant_id nullable (batch can cover multiple merchants)
ALTER TABLE settlement_batches ALTER COLUMN merchant_id DROP NOT NULL;

-- Payout items within settlement batches
CREATE TABLE IF NOT EXISTS payout_items (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id    UUID NOT NULL REFERENCES settlement_batches(id) ON DELETE CASCADE,
  merchant_id UUID NOT NULL REFERENCES merchants(id),
  amount      NUMERIC(18,2) NOT NULL,
  reference   TEXT NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'confirmed', 'failed')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_payout_items_batch ON payout_items (batch_id);
CREATE INDEX IF NOT EXISTS idx_payout_items_status ON payout_items (status);

-- Extend reconciliation_exceptions
ALTER TABLE reconciliation_exceptions ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES settlement_batches(id);
ALTER TABLE reconciliation_exceptions ADD COLUMN IF NOT EXISTS payout_item_id UUID REFERENCES payout_items(id);
ALTER TABLE reconciliation_exceptions ADD COLUMN IF NOT EXISTS resolution_notes TEXT;

-- Add category to support_tickets
ALTER TABLE support_tickets ADD COLUMN IF NOT EXISTS category TEXT;

-- Support ticket messages (thread)
CREATE TABLE IF NOT EXISTS support_ticket_messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   UUID NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  author_id   UUID NOT NULL REFERENCES auth.users(id),
  author_role TEXT NOT NULL DEFAULT 'user'
                CHECK (author_role IN ('user', 'support', 'admin')),
  body        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON support_ticket_messages (ticket_id);

-- App config (key-value store for limits, feature flags)
CREATE TABLE IF NOT EXISTS app_config (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO app_config (key, value) VALUES
  ('max_balance_adjustment', '10000')
ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- RLS for new tables
-- ============================================================

ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchant_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE payout_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_ticket_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY devices_read ON devices
  FOR SELECT USING (user_id = auth.uid() OR public.has_admin_role());

CREATE POLICY merchant_profiles_read ON merchant_profiles
  FOR SELECT USING (user_id = auth.uid() OR public.has_admin_role());

CREATE POLICY payout_items_admin_read ON payout_items
  FOR SELECT USING (public.has_admin_role());

CREATE POLICY ticket_messages_read ON support_ticket_messages
  FOR SELECT USING (public.has_admin_role() OR author_id = auth.uid());

CREATE POLICY app_config_admin_read ON app_config
  FOR SELECT USING (public.has_admin_role());
