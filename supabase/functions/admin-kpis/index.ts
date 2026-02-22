import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Verify the caller is authenticated with an admin role
    const authHeader = req.headers.get("Authorization");
    if (!authHeader) {
      return new Response(JSON.stringify({ error: "Missing authorization" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    // Create a client scoped to the calling user to verify their role
    const userClient = createClient(supabaseUrl, Deno.env.get("SUPABASE_ANON_KEY")!, {
      global: { headers: { Authorization: authHeader } },
    });

    const {
      data: { user },
      error: authError,
    } = await userClient.auth.getUser();

    if (authError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Use service role client for admin queries
    const adminClient = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    // Check admin role
    const { data: roles } = await adminClient
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .in("role", ["admin", "compliance", "finance", "support"]);

    if (!roles || roles.length === 0) {
      return new Response(JSON.stringify({ error: "Forbidden" }), {
        status: 403,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Fetch KPIs in parallel
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const todayIso = todayStart.toISOString();

    const [usersRes, merchantsRes, volumeRes, feesRes, failedRes, newUsersRes] =
      await Promise.all([
        adminClient
          .from("profiles")
          .select("id", { count: "exact", head: true }),
        adminClient
          .from("merchant_profiles")
          .select("id", { count: "exact", head: true }),
        adminClient
          .from("transactions")
          .select("amount")
          .gte("created_at", todayIso)
          .eq("status", "completed"),
        adminClient
          .from("transactions")
          .select("fee")
          .gte("created_at", todayIso)
          .eq("status", "completed"),
        adminClient
          .from("transactions")
          .select("id", { count: "exact", head: true })
          .gte("created_at", todayIso)
          .eq("status", "failed"),
        adminClient
          .from("profiles")
          .select("id", { count: "exact", head: true })
          .gte("created_at", todayIso),
      ]);

    const todayVolume = (volumeRes.data ?? []).reduce(
      (sum: number, t: { amount: number }) => sum + Number(t.amount),
      0
    );
    const todayFees = (feesRes.data ?? []).reduce(
      (sum: number, t: { fee: number }) => sum + Number(t.fee),
      0
    );

    const kpis = {
      total_users: usersRes.count ?? 0,
      total_merchants: merchantsRes.count ?? 0,
      today_volume: todayVolume,
      today_fees: todayFees,
      failed_tx_count: failedRes.count ?? 0,
      new_users_today: newUsersRes.count ?? 0,
    };

    // Write audit log for dashboard view
    await adminClient.from("audit_logs").insert({
      actor_id: user.id,
      action: "admin.dashboard.view_kpis",
      resource_type: "dashboard",
      metadata: {},
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify(kpis), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
});
