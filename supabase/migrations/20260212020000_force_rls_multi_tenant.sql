-- PostgreSQL Best Practices: FORCE ROW LEVEL SECURITY for multi-tenant tables
-- Migration: 20260212020000_force_rls_multi_tenant.sql
-- Reference: .cursor/rules/supabase-postgres-best-practices.mdc
--
-- FORCE ROW LEVEL SECURITY ensures table owners (including service_role) also
-- respect RLS policies. Critical for user-scoped data.

ALTER TABLE options_strategies FORCE ROW LEVEL SECURITY;
ALTER TABLE options_legs FORCE ROW LEVEL SECURITY;
ALTER TABLE options_leg_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE options_multi_leg_alerts FORCE ROW LEVEL SECURITY;
ALTER TABLE options_strategy_metrics FORCE ROW LEVEL SECURITY;
ALTER TABLE multi_leg_journal FORCE ROW LEVEL SECURITY;
ALTER TABLE user_alert_preferences FORCE ROW LEVEL SECURITY;
