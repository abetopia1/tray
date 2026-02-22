import { createClient } from '@supabase/supabase-js';

/**
 * Server-only Supabase client using the service role key.
 * Used exclusively by Edge Functions and server-side operations
 * that need to bypass RLS for privileged writes (e.g., audit logs).
 *
 * NEVER import this from client-side code.
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    throw new Error('Missing SUPABASE_SERVICE_ROLE_KEY or NEXT_PUBLIC_SUPABASE_URL');
  }

  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}
