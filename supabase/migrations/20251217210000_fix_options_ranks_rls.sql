-- Fix RLS policy for options_ranks to allow anon reads
-- The table was only readable by authenticated users, but the Swift app uses anon key

-- Drop the existing authenticated-only policy
DROP POLICY IF EXISTS "options_ranks_select_authenticated" ON options_ranks;

-- Create new policy allowing anon reads
CREATE POLICY "options_ranks_select_anon" ON options_ranks
    FOR SELECT TO anon, authenticated
    USING (true);

-- Keep the service role policy for writes
-- (Already exists: options_ranks_service_all)
