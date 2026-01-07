-- Force schema refresh for SPEC-8 tables

-- Grant permissions to all roles
grant usage on schema public to anon, authenticated, service_role;
grant all on all tables in schema public to anon, authenticated, service_role;
grant all on all sequences in schema public to anon, authenticated, service_role;
grant all on all functions in schema public to anon, authenticated, service_role;

-- Specific grants for SPEC-8 tables
grant select, insert, update, delete on job_definitions to anon, authenticated, service_role;
grant select, insert, update, delete on job_runs to anon, authenticated, service_role;
grant select, insert, update, delete on coverage_status to anon, authenticated, service_role;

-- Grant on sequences
grant usage, select on all sequences in schema public to anon, authenticated, service_role;

-- Force PostgREST schema reload
notify pgrst, 'reload schema';

-- Verify tables exist
select table_name, table_type 
from information_schema.tables 
where table_schema = 'public' 
  and table_name in ('job_definitions', 'job_runs', 'coverage_status', 'ohlc_bars_v2')
order by table_name;

-- Verify RLS policies
select schemaname, tablename, policyname, permissive, roles, cmd
from pg_policies
where tablename in ('job_definitions', 'job_runs', 'coverage_status')
order by tablename, policyname;
