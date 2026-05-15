// deno-lint-ignore-file no-explicit-any
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.47.0";

export interface HermesJob {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  attempts: number;
  max_attempts: number;
}

export interface HermesContext {
  admin: SupabaseClient;
  job: HermesJob;
}

export type HermesHandler = (ctx: HermesContext) => Promise<Record<string, unknown> | void>;

// Registry of job handlers. Add new types here as they are implemented.
export const HERMES_HANDLERS: Record<string, HermesHandler> = {
  // No-op handler — useful for smoke-testing the worker.
  "noop": async ({ job }) => {
    return { echoed: job.payload };
  },
};

export function isKnownJobType(type: string): boolean {
  return Object.prototype.hasOwnProperty.call(HERMES_HANDLERS, type);
}
