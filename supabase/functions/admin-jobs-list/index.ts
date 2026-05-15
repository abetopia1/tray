import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

/**
 * List recent Hermes jobs. Admin-only.
 *
 * GET / POST body: { status?: string, type?: string, limit?: number }
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

    const admin = createClient(supabaseUrl, serviceRoleKey, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    const { data: roles } = await admin
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .eq("role", "admin");

    if (!roles || roles.length === 0) {
      return new Response(JSON.stringify({ error: "Forbidden" }), {
        status: 403,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    let body: { status?: string; type?: string; limit?: number } = {};
    if (req.method === "POST") {
      try { body = await req.json(); } catch { /* ignore */ }
    }

    const limit = Math.min(Math.max(body.limit ?? 50, 1), 200);

    let query = admin
      .from("hermes_jobs")
      .select("id,type,status,priority,attempts,max_attempts,last_error,run_at,claimed_at,claimed_by,completed_at,enqueued_by,created_at")
      .order("created_at", { ascending: false })
      .limit(limit);

    if (body.status) query = query.eq("status", body.status);
    if (body.type) query = query.eq("type", body.type);

    const { data: jobs, error } = await query;
    if (error) throw error;

    const counts = await admin
      .from("hermes_jobs")
      .select("status", { count: "exact", head: false });

    const summary = (counts.data ?? []).reduce<Record<string, number>>((acc, row: { status: string }) => {
      acc[row.status] = (acc[row.status] ?? 0) + 1;
      return acc;
    }, {});

    return new Response(JSON.stringify({ jobs: jobs ?? [], summary }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
