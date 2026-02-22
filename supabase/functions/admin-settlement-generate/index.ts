import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

/**
 * Generate a settlement batch for a given date.
 * Aggregates completed merchant_payment transactions since last cutoff.
 *
 * POST body: { run_date: "YYYY-MM-DD" }
 */
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
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
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const adminClient = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    // Verify admin/finance role
    const { data: roles } = await adminClient
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .in("role", ["admin", "finance"]);

    if (!roles || roles.length === 0) {
      return new Response(JSON.stringify({ error: "Forbidden" }), {
        status: 403,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const runDate = body.run_date;
    if (!runDate) {
      return new Response(JSON.stringify({ error: "run_date required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Calculate cutoff: end of run_date day
    const cutoffAt = new Date(runDate + "T23:59:59.999Z").toISOString();
    const dayStart = new Date(runDate + "T00:00:00.000Z").toISOString();

    // Aggregate completed merchant_payment transactions for the day
    const { data: txData } = await adminClient
      .from("transactions")
      .select("merchant_id, amount, fee")
      .eq("tx_type", "merchant_payment")
      .eq("status", "completed")
      .gte("created_at", dayStart)
      .lte("created_at", cutoffAt);

    const transactions = txData ?? [];
    const grossAmount = transactions.reduce((s: number, t: { amount: number }) => s + Number(t.amount), 0);
    const totalFees = transactions.reduce((s: number, t: { fee: number }) => s + Number(t.fee), 0);
    const netAmount = grossAmount - totalFees;

    // Create settlement batch
    const { data: batch, error: batchError } = await adminClient
      .from("settlement_batches")
      .insert({
        run_date: runDate,
        cutoff_at: cutoffAt,
        gross_amount: grossAmount,
        total_fees: totalFees,
        net_amount: netAmount,
        item_count: transactions.length,
        status: "pending",
      })
      .select()
      .single();

    if (batchError) throw batchError;

    // Create payout items per merchant
    const merchantTotals: Record<string, number> = {};
    for (const tx of transactions) {
      const mid = (tx as { merchant_id: string }).merchant_id;
      if (mid) {
        merchantTotals[mid] = (merchantTotals[mid] ?? 0) + Number((tx as { amount: number }).amount) - Number((tx as { fee: number }).fee);
      }
    }

    const payoutItems = Object.entries(merchantTotals).map(([merchantId, amount]) => ({
      batch_id: batch.id,
      merchant_id: merchantId,
      amount,
      reference: `PAY-${batch.id.slice(0, 8)}-${merchantId.slice(0, 8)}`,
      status: "pending",
    }));

    if (payoutItems.length > 0) {
      await adminClient.from("payout_items").insert(payoutItems);
    }

    // Audit log
    await adminClient.from("audit_logs").insert({
      actor_id: user.id,
      action: "settlement.generate_batch",
      resource_type: "settlement_batches",
      resource_id: batch.id,
      metadata: { run_date: runDate, gross: grossAmount, fees: totalFees, net: netAmount, items: transactions.length },
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify(batch), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
