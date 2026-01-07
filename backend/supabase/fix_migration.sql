-- Remove the duplicate migration entries so we can reapply with fixed SQL
delete from supabase_migrations.schema_migrations 
where version in ('20260106000000', '20260106000001');

-- Verify removal
select version, name from supabase_migrations.schema_migrations 
where version >= '20260106000000'
order by version;
