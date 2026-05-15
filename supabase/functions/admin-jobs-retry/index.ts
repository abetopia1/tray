import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

/**
 * Re-queue a failed Hermes job. Admin-only.
 *
 * POST body: { id: string }
 *
 * Resets status to pending, run_at to now, and clears the failure
 * bookkeeping. Attempt count is preserved so a chronically broken
 * handler still trips max_attempts on the next run.
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

    const body = await req.json();
    const id = String(body?.id ?? "").trim();
    if (!id) {
      return new Response(JSON.stringify({ error: "id required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Bump max_attempts so a previously exhausted job has at least
    // one more shot after a manual retry.
    const { data: existing } = await admin
      .from("hermes_jobs")
      .select("attempts, max_attempts, status")
      .eq("id", id)
      .single();

    if (!existing) {
      return new Response(JSON.stringify({ error: "Not found" }), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const newMax = Math.max(existing.max_attempts, existing.attempts + 1);

    const { data: job, error } = await admin
      .from("hermes_jobs")
      .update({
        status: "pending",
        run_at: new Date().toISOString(),
        max_attempts: newMax,
        last_error: null,
        claimed_at: null,
        claimed_by: null,
        completed_at: null,
        updated_at: new Date().toISOString(),
      })
      .eq("id", id)
      .select()
      .single();

    if (error) throw error;

    await admin.from("audit_logs").insert({
      actor_id: user.id,
      action: "hermes.retry",
      resource_type: "hermes_jobs",
      resource_id: id,
      metadata: { previous_status: existing.status, attempts: existing.attempts },
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify(job), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
