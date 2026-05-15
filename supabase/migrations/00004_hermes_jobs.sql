-- ============================================================
-- Hermes: background job queue
-- ============================================================
-- A simple postgres-backed job queue. Jobs are claimed atomically
-- via FOR UPDATE SKIP LOCKED so multiple workers can run safely.

CREATE TABLE IF NOT EXISTS hermes_jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type          TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}',
  status        TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
  priority      INT NOT NULL DEFAULT 100,
  attempts      INT NOT NULL DEFAULT 0,
  max_attempts  INT NOT NULL DEFAULT 3,
  last_error    TEXT,
  run_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  claimed_at    TIMESTAMPTZ,
  claimed_by    TEXT,
  completed_at  TIMESTAMPTZ,
  enqueued_by   UUID REFERENCES auth.users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hermes_jobs_status_run_at
  ON hermes_jobs (status, run_at)
  WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_hermes_jobs_type ON hermes_jobs (type);
CREATE INDEX IF NOT EXISTS idx_hermes_jobs_created ON hermes_jobs (created_at DESC);

-- Atomic claim: pick up to `batch_size` due pending jobs and mark them
-- as running. Skips locked rows so concurrent workers don't collide.
CREATE OR REPLACE FUNCTION public.hermes_claim_jobs(
  worker_id TEXT,
  batch_size INT DEFAULT 5
)
RETURNS SETOF hermes_jobs
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  WITH due AS (
    SELECT id
    FROM hermes_jobs
    WHERE status = 'pending'
      AND run_at <= now()
    ORDER BY priority ASC, run_at ASC
    LIMIT batch_size
    FOR UPDATE SKIP LOCKED
  )
  UPDATE hermes_jobs j
  SET status = 'running',
      claimed_at = now(),
      claimed_by = worker_id,
      attempts = j.attempts + 1,
      updated_at = now()
  FROM due
  WHERE j.id = due.id
  RETURNING j.*;
END;
$$;

ALTER TABLE hermes_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY hermes_jobs_admin_read ON hermes_jobs
  FOR SELECT USING (public.has_admin_role());
