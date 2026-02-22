import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

/**
 * Parse a bank confirmation CSV and reconcile payout items.
 *
 * POST body: { batch_id: string, csv_content: string }
 *
 * Expected CSV format (header row + data):
 *   reference,merchant_id,amount,status
 *
 * The function matches by reference and amount, then marks payout_items
 * as confirmed or failed. Unmatched rows create reconciliation_exceptions.
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

    // Verify admin/finance role
    const { data: roles } = await adminClient
      .from("user_roles").select("role").eq("user_id", user.id).in("role", ["admin", "finance"]);
    if (!roles || roles.length === 0) {
      return new Response(JSON.stringify({ error: "Forbidden" }), {
        status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json();
    const { batch_id, csv_content } = body;
    if (!batch_id || !csv_content) {
      return new Response(JSON.stringify({ error: "batch_id and csv_content required" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Parse CSV
    const lines = csv_content.trim().split("\n");
    if (lines.length < 2) {
      return new Response(JSON.stringify({ error: "CSV must have header + data rows" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const rows = lines.slice(1).map((line: string) => {
      const [reference, merchant_id, amount, status] = line.split(",").map((s: string) => s.trim());
      return { reference, merchant_id, amount: parseFloat(amount), status: status?.toLowerCase() };
    });

    // Fetch payout items for this batch
    const { data: payoutItems } = await adminClient
      .from("payout_items").select("*").eq("batch_id", batch_id);
    const items = payoutItems ?? [];
    const itemsByRef = new Map(items.map((i: { reference: string }) => [i.reference, i]));

    let matched = 0;
    let unmatched = 0;
    let failed = 0;

    for (const row of rows) {
      const item = itemsByRef.get(row.reference) as { id: string; amount: number; merchant_id: string } | undefined;

      if (item && Math.abs(Number(item.amount) - row.amount) < 0.01) {
        // Match found
        const newStatus = (row.status === "confirmed" || row.status === "success") ? "confirmed" : "failed";
        await adminClient.from("payout_items").update({ status: newStatus }).eq("id", item.id);
        if (newStatus === "confirmed") matched++;
        else failed++;
      } else {
        // No match — create reconciliation exception
        unmatched++;
        await adminClient.from("reconciliation_exceptions").insert({
          batch_id,
          payout_item_id: item?.id ?? null,
          reason: item
            ? `Amount mismatch: expected ${item.amount}, got ${row.amount}`
            : `No payout item found for reference: ${row.reference}`,
          status: "open",
        });
      }
    }

    // Audit log
    await adminClient.from("audit_logs").insert({
      actor_id: user.id,
      action: "recon.upload_confirmation",
      resource_type: "settlement_batches",
      resource_id: batch_id,
      metadata: { rows: rows.length, matched, unmatched, failed },
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify({ matched, unmatched, failed, total_rows: rows.length }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
