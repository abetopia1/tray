import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";
import { isKnownJobType } from "../_shared/hermes_handlers.ts";

/**
 * Enqueue a Hermes job. Admin-only.
 *
 * POST body: {
 *   type: string,           // must be a registered handler
 *   payload?: object,
 *   priority?: number,      // lower = higher priority, default 100
 *   run_at?: string,        // ISO timestamp; default now
 *   max_attempts?: number   // default 3
 * }
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
    const type = String(body?.type ?? "").trim();
    if (!type) {
      return new Response(JSON.stringify({ error: "type required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }
    if (!isKnownJobType(type)) {
      return new Response(JSON.stringify({ error: `unknown job type: ${type}` }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { data: job, error: insertError } = await admin
      .from("hermes_jobs")
      .insert({
        type,
        payload: body?.payload ?? {},
        priority: typeof body?.priority === "number" ? body.priority : 100,
        run_at: body?.run_at ?? new Date().toISOString(),
        max_attempts: typeof body?.max_attempts === "number" ? body.max_attempts : 3,
        enqueued_by: user.id,
      })
      .select()
      .single();

    if (insertError) throw insertError;

    await admin.from("audit_logs").insert({
      actor_id: user.id,
      action: "hermes.enqueue",
      resource_type: "hermes_jobs",
      resource_id: job.id,
      metadata: { type, priority: job.priority },
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
