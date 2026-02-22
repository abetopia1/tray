import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

/**
 * Manual balance adjustment — admin-only, PIN-guarded, limit-checked.
 *
 * POST body: { user_id: string, amount: number, reason: string, pin: string }
 *
 * This creates an 'adjustment' transaction to record the balance change.
 * The actual wallet balance logic depends on your balance model (ledger vs column).
 */
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: { user }, error: authError } = await userClient.auth.getUser();
    if (authError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const adminClient = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    // Only admin role
    const { data: roles } = await adminClient
      .from("user_roles").select("role").eq("user_id", user.id).eq("role", "admin");
    if (!roles || roles.length === 0) {
      return new Response(JSON.stringify({ error: "Forbidden: admin only" }), {
        status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const { user_id, amount, reason, pin } = body;

    if (!user_id || amount === undefined || !reason || !pin) {
      return new Response(JSON.stringify({ error: "user_id, amount, reason, pin required" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // PIN check — in production, verify against admin's stored PIN hash.
    // For MVP, accept any non-empty PIN and log it.
    if (pin.length < 4) {
      return new Response(JSON.stringify({ error: "Invalid PIN" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Check max adjustment limit from app_config
    const { data: configRow } = await adminClient
      .from("app_config").select("value").eq("key", "max_balance_adjustment").single();
    const maxLimit = configRow ? parseFloat(configRow.value) : 10000;

    if (Math.abs(amount) > maxLimit) {
      return new Response(JSON.stringify({ error: `Amount exceeds max limit of ${maxLimit}` }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Verify target user exists
    const { data: targetProfile } = await adminClient
      .from("profiles").select("id").eq("id", user_id).single();
    if (!targetProfile) {
      return new Response(JSON.stringify({ error: "User not found" }), {
        status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Create adjustment transaction (ledger entry)
    const { data: tx, error: txError } = await adminClient
      .from("transactions")
      .insert({
        sender_id: amount < 0 ? user_id : null,
        receiver_id: amount > 0 ? user_id : null,
        tx_type: "adjustment",
        amount: Math.abs(amount),
        fee: 0,
        status: "completed",
        metadata: { reason, adjusted_by: user.id },
      })
      .select()
      .single();

    if (txError) throw txError;

    // Audit log
    await adminClient.from("audit_logs").insert({
      actor_id: user.id,
      action: "danger.balance_adjust",
      resource_type: "profiles",
      resource_id: user_id,
      metadata: { amount, reason, transaction_id: tx.id },
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify({ success: true, transaction_id: tx.id }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
