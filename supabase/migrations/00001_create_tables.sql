-- ============================================================
-- Tray Admin Dashboard - Database Schema
-- ============================================================

-- Profiles (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  phone_e164  TEXT,
  handle      TEXT UNIQUE,
  full_name   TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_profiles_phone ON profiles (phone_e164);
CREATE INDEX idx_profiles_handle ON profiles (handle);
CREATE INDEX idx_profiles_full_name ON profiles USING gin (full_name gin_trgm_ops);

-- User roles (admin, compliance, finance, support)
CREATE TABLE IF NOT EXISTS user_roles (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role       TEXT NOT NULL CHECK (role IN ('admin', 'compliance', 'finance', 'support')),
  granted_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, role)
);

CREATE INDEX idx_user_roles_user ON user_roles (user_id);
CREATE INDEX idx_user_roles_role ON user_roles (role);

-- Merchants
CREATE TABLE IF NOT EXISTS merchants (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'active', 'suspended', 'rejected')),
  owner_id   UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_merchants_status ON merchants (status);

-- Transactions
CREATE TABLE IF NOT EXISTS transactions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID NOT NULL REFERENCES merchants(id),
  amount      NUMERIC(18,2) NOT NULL,
  fee         NUMERIC(18,2) NOT NULL DEFAULT 0,
  currency    TEXT NOT NULL DEFAULT 'USD',
  status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'failed', 'reversed')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_merchant ON transactions (merchant_id);
CREATE INDEX idx_transactions_status ON transactions (status);
CREATE INDEX idx_transactions_created ON transactions (created_at);

-- KYC reviews
CREATE TABLE IF NOT EXISTS kyc_reviews (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status     TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'approved', 'rejected')),
  reviewer_id UUID REFERENCES auth.users(id),
  notes      TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kyc_status ON kyc_reviews (status);

-- Settlement batches
CREATE TABLE IF NOT EXISTS settlement_batches (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  merchant_id UUID NOT NULL REFERENCES merchants(id),
  amount      NUMERIC(18,2) NOT NULL,
  currency    TEXT NOT NULL DEFAULT 'USD',
  status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  settled_at  TIMESTAMPTZ
);

CREATE INDEX idx_settlement_status ON settlement_batches (status);

-- Reconciliation exceptions
CREATE TABLE IF NOT EXISTS reconciliation_exceptions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id UUID REFERENCES transactions(id),
  reason         TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'open'
                   CHECK (status IN ('open', 'investigating', 'resolved')),
  resolved_by    UUID REFERENCES auth.users(id),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ
);

CREATE INDEX idx_recon_status ON reconciliation_exceptions (status);

-- Support tickets
CREATE TABLE IF NOT EXISTS support_tickets (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES auth.users(id),
  subject     TEXT NOT NULL,
  description TEXT,
  priority    TEXT NOT NULL DEFAULT 'medium'
                CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
  status      TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
  assigned_to UUID REFERENCES auth.users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tickets_status ON support_tickets (status);

-- Audit logs (append-only)
CREATE TABLE IF NOT EXISTS audit_logs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id      UUID REFERENCES auth.users(id),
  action        TEXT NOT NULL,
  resource_type TEXT,
  resource_id   TEXT,
  metadata      JSONB DEFAULT '{}',
  ip_address    INET,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_actor ON audit_logs (actor_id);
CREATE INDEX idx_audit_action ON audit_logs (action);
CREATE INDEX idx_audit_resource ON audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs (created_at);
