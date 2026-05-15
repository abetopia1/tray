import { createClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";
import { corsHeaders } from "../_shared/cors.ts";
import { HERMES_HANDLERS, type HermesJob } from "../_shared/hermes_handlers.ts";

/**
 * Hermes worker. Claims a batch of due jobs and runs them.
 *
 * Invocation:
 *   - Scheduled (cron) via Supabase pg_cron / scheduled trigger
 *   - Manual via Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>
 *
 * Optional POST body: { batch_size?: number }
 *
 * On success: status -> completed, last_error cleared.
 * On failure: status -> pending (with exponential backoff) until attempts >= max_attempts,
 * then status -> failed.
 */
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  // Worker is service-only. Reject anything that isn't the service role key.
  const authHeader = req.headers.get("Authorization") ?? "";
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
  if (authHeader !== `Bearer ${serviceRoleKey}`) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
  const admin = createClient(supabaseUrl, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  let batchSize = 5;
  if (req.method === "POST") {
    try {
      const body = await req.json();
      if (typeof body?.batch_size === "number" && body.batch_size > 0 && body.batch_size <= 50) {
        batchSize = Math.floor(body.batch_size);
      }
    } catch {
      // empty body is fine
    }
  }

  const workerId = `hermes-${crypto.randomUUID()}`;

  const { data: claimed, error: claimError } = await admin.rpc("hermes_claim_jobs", {
    worker_id: workerId,
    batch_size: batchSize,
  });

  if (claimError) {
    return new Response(
      JSON.stringify({ error: "claim_failed", detail: claimError.message }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }

  const jobs = (claimed ?? []) as HermesJob[];
  const results: Array<{ id: string; status: string; error?: string }> = [];

  for (const job of jobs) {
    const handler = HERMES_HANDLERS[job.type];

    if (!handler) {
      // Unknown type: fail terminally so it doesn't loop.
      await admin
        .from("hermes_jobs")
        .update({
          status: "failed",
          last_error: `unknown job type: ${job.type}`,
          completed_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq("id", job.id);
      results.push({ id: job.id, status: "failed", error: "unknown_type" });
      continue;
    }

    try {
      const result = await handler({ admin, job });
      await admin
        .from("hermes_jobs")
        .update({
          status: "completed",
          last_error: null,
          completed_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          payload: { ...job.payload, _result: result ?? null },
        })
        .eq("id", job.id);
      results.push({ id: job.id, status: "completed" });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const exhausted = job.attempts >= job.max_attempts;

      // Exponential backoff: 30s, 2m, 8m, capped at 30m.
      const backoffSec = Math.min(30 * Math.pow(4, job.attempts - 1), 30 * 60);
      const nextRun = new Date(Date.now() + backoffSec * 1000).toISOString();

      await admin
        .from("hermes_jobs")
        .update({
          status: exhausted ? "failed" : "pending",
          last_error: message,
          claimed_at: null,
          claimed_by: null,
          run_at: exhausted ? job.run_at : nextRun,
          completed_at: exhausted ? new Date().toISOString() : null,
          updated_at: new Date().toISOString(),
        })
        .eq("id", job.id);

      results.push({
        id: job.id,
        status: exhausted ? "failed" : "retry_scheduled",
        error: message,
      });
    }
  }

  return new Response(
    JSON.stringify({ worker_id: workerId, processed: results.length, results }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" } }
  );
});
