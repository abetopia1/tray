import { createClient } from '@/lib/supabase/client';

/**
 * Write an audit log entry via the admin-audit Edge Function.
 * This ensures no privileged DB writes happen from the client.
 */
export async function writeAuditLog(params: {
  action: string;
  resource_type?: string;
  resource_id?: string;
  metadata?: Record<string, unknown>;
}) {
  const supabase = createClient();
  const { error } = await supabase.functions.invoke('admin-audit', {
    body: params,
  });
  if (error) {
    console.error('Audit log write failed:', error);
  }
}
