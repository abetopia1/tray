-- ============================================================
-- Row Level Security Policies
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE kyc_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE settlement_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE reconciliation_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function: check if the current user has an admin role
CREATE OR REPLACE FUNCTION public.has_admin_role()
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM user_roles
    WHERE user_id = auth.uid()
      AND role IN ('admin', 'compliance', 'finance', 'support')
  );
$$;

-- Profiles: users see their own, admins see all
CREATE POLICY profiles_self_read ON profiles
  FOR SELECT USING (id = auth.uid() OR public.has_admin_role());

CREATE POLICY profiles_self_update ON profiles
  FOR UPDATE USING (id = auth.uid());

-- User roles: only admins can read
CREATE POLICY user_roles_admin_read ON user_roles
  FOR SELECT USING (public.has_admin_role() OR user_id = auth.uid());

-- User roles: no direct inserts/updates from client (use Edge Functions)
-- Service role key bypasses RLS for Edge Functions

-- Merchants: admins read all, owners read own
CREATE POLICY merchants_read ON merchants
  FOR SELECT USING (public.has_admin_role() OR owner_id = auth.uid());

-- Transactions: admins read all
CREATE POLICY transactions_admin_read ON transactions
  FOR SELECT USING (public.has_admin_role());

-- KYC: admins read all, users read own
CREATE POLICY kyc_admin_read ON kyc_reviews
  FOR SELECT USING (public.has_admin_role() OR user_id = auth.uid());

-- Settlement batches: admins only
CREATE POLICY settlement_admin_read ON settlement_batches
  FOR SELECT USING (public.has_admin_role());

-- Reconciliation exceptions: admins only
CREATE POLICY recon_admin_read ON reconciliation_exceptions
  FOR SELECT USING (public.has_admin_role());

-- Support tickets: admins read all, users read own
CREATE POLICY tickets_read ON support_tickets
  FOR SELECT USING (public.has_admin_role() OR user_id = auth.uid());

-- Audit logs: admins read only, no client writes (Edge Functions write via service role)
CREATE POLICY audit_admin_read ON audit_logs
  FOR SELECT USING (public.has_admin_role());
