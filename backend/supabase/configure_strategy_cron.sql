-- Cron schedule for strategy backtest worker
-- Run every minute to process pending backtest jobs

-- Unschedule existing job if it exists
SELECT cron.unschedule('strategy-backtest-worker');

-- Schedule the worker to run every minute
SELECT cron.schedule(
  'strategy-backtest-worker',
  '* * * * *',  -- Every minute
  $$
  SELECT net.http_post(
    url := '${DENO_DEPLOY_URL}/functions/v1/strategy-backtest-worker',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true)
    ),
    body := jsonb_build_object('cron', true)
  );
  $$
);

COMMENT ON FUNCTION cron.schedule IS 'Runs strategy-backtest-worker every minute to process pending backtest jobs';
