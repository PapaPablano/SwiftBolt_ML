-- Orchestrator heartbeat tracking

create table if not exists orchestrator_heartbeat (
  name text primary key,
  last_seen timestamptz not null default now(),
  status text not null default 'healthy' check (status in ('healthy', 'warning', 'error')),
  message text,
  updated_at timestamptz not null default now()
);

create index if not exists orchestrator_heartbeat_last_seen_idx
  on orchestrator_heartbeat (last_seen desc);

alter table orchestrator_heartbeat enable row level security;

-- Ensure updated_at is refreshed on updates
create trigger update_orchestrator_heartbeat_updated_at
  before update on orchestrator_heartbeat
  for each row
  execute function update_updated_at_column();
