import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";

Deno.serve(async (req: Request) => {
  // Handle CORS preflight
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

    // Verify caller identity
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

    // Service role client for admin operations
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

    // Parse search query
    const body = await req.json();
    const query = (body.query ?? "").trim();

    if (!query || query.length < 2) {
      return new Response(
        JSON.stringify({ results: [], error: "Query must be at least 2 characters" }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    // Sanitize: limit to 50 characters to prevent abuse
    const sanitizedQuery = query.slice(0, 50);

    // Search by phone_e164 (exact prefix), handle (ilike), or full_name (ilike)
    const { data: results, error: searchError } = await adminClient
      .from("profiles")
      .select("id, phone_e164, handle, full_name, kyc_status, wallet_status")
      .or(
        `phone_e164.ilike.%${sanitizedQuery}%,handle.ilike.%${sanitizedQuery}%,full_name.ilike.%${sanitizedQuery}%`
      )
      .limit(20);

    if (searchError) {
      throw searchError;
    }

    // Write audit log for search action
    await adminClient.from("audit_logs").insert({
      actor_id: user.id,
      action: "admin.search.users",
      resource_type: "profiles",
      metadata: { query: sanitizedQuery, result_count: results?.length ?? 0 },
      ip_address: req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    });

    return new Response(JSON.stringify({ results: results ?? [] }), {
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
