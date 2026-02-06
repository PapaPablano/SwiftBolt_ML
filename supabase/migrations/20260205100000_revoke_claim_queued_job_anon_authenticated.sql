-- Restrict claim_queued_job() to service_role only.
-- Orchestrator (supabase/functions/orchestrator) is the only caller; it uses
-- createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) and passes that client
-- to dispatchQueuedJobs -> supabase.rpc('claim_queued_job'). Anon/authenticated
-- lack RLS rights to UPDATE job_runs and caused 500s.

REVOKE EXECUTE ON FUNCTION public.claim_queued_job() FROM anon;
REVOKE EXECUTE ON FUNCTION public.claim_queued_job() FROM authenticated;

-- service_role retains execute via default ownership; explicit grant for clarity
GRANT EXECUTE ON FUNCTION public.claim_queued_job() TO service_role;

COMMENT ON FUNCTION public.claim_queued_job() IS
  'Claims next queued job_runs row (FOR UPDATE SKIP LOCKED) and marks it running. Callable by service_role only; orchestrator uses SUPABASE_SERVICE_ROLE_KEY.';
