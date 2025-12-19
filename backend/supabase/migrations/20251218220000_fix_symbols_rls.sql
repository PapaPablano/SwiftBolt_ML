-- Fix RLS policy for symbols to allow anon reads
-- The table was only readable by authenticated users, but the Swift app and Edge Functions need anon key access

-- Drop the existing authenticated-only policy
DROP POLICY IF EXISTS "symbols_select_authenticated" ON symbols;

-- Create new policy allowing anon reads
CREATE POLICY "symbols_select_anon" ON symbols
    FOR SELECT TO anon, authenticated
    USING (true);

-- Keep the service role policy for writes
-- (Already exists: symbols_service_all)
