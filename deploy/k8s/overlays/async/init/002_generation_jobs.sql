CREATE TABLE IF NOT EXISTS generation_jobs (
    job_id text PRIMARY KEY,
    status text NOT NULL,
    queue_backend text NOT NULL,
    queue_job_id text,
    request_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    response_summary jsonb,
    error_detail text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS generation_jobs_status_created_at_idx
    ON generation_jobs (status, created_at DESC);
