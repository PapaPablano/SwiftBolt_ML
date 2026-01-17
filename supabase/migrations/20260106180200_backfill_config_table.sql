-- SPEC-8: Configuration table for backfill worker
-- Alternative to database settings which require superuser privileges

-- Create config table for storing service credentials
create table if not exists backfill_config (
  key text primary key,
  value text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Insert the service role key (replace with your actual key)
insert into backfill_config (key, value)
values ('service_role_key', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5Z2ZsYWVtdG13aXdhdmljbGtzIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTIxMTMzNiwiZXhwIjoyMDgwNzg3MzM2fQ.YajeNHOQ63uBDDZhJ2YYHK7L-BKmnZAviDqrlk2TQxU')
on conflict (key) do update set value = excluded.value, updated_at = now();

-- RLS: Only service_role can read this table
alter table backfill_config enable row level security;

create policy "Service role only"
  on backfill_config
  for all
  to service_role
  using (true)
  with check (true);

-- Grant access to service_role
grant all on backfill_config to service_role;

-- Update the cron job to read from the config table
do $$
begin
  perform cron.unschedule('backfill-worker-every-minute');
exception when others then
  null;
end $$;

select cron.schedule(
  'backfill-worker-every-minute',
  '* * * * *',
  $$
    select net.http_post(
      url := 'https://cygflaemtmwiwaviclks.supabase.co/functions/v1/run-backfill-worker',
      headers := jsonb_build_object(
        'Content-Type', 'application/json',
        'Authorization', 'Bearer ' || (select value from backfill_config where key = 'service_role_key')
      ),
      body := '{}',
      timeout_milliseconds := 29000
    );
  $$
);

comment on table backfill_config is 'Configuration storage for backfill worker credentials';
