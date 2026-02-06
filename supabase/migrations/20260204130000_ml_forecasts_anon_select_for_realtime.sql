-- Allow anon to SELECT ml_forecasts so Realtime postgres_changes can deliver rows to the WebView (anon key).
-- Realtime respects RLS; without this policy, subscription succeeds but no events are emitted.
DROP POLICY IF EXISTS "ml_forecasts_select_anon" ON public.ml_forecasts;
CREATE POLICY "ml_forecasts_select_anon" ON public.ml_forecasts
    FOR SELECT TO anon
    USING (true);
