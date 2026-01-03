-- Migration: Preserve forecast evaluations
--
-- Changes forecast_evaluations.forecast_id FK from ON DELETE CASCADE to
-- ON DELETE SET NULL so evaluations aren't wiped when forecasts are deleted.

-- Step 1: Change forecast_evaluations.forecast_id FK to ON DELETE SET NULL
-- This prevents cascade deletion of evaluations when forecasts are removed.
DO $$
DECLARE
    fk_name text;
BEGIN
    -- Find the FK constraint name for forecast_id -> ml_forecasts(id)
    SELECT tc.constraint_name
      INTO fk_name
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON kcu.constraint_name = tc.constraint_name
       AND kcu.table_schema = tc.table_schema
     WHERE tc.table_schema = 'public'
       AND tc.table_name = 'forecast_evaluations'
       AND tc.constraint_type = 'FOREIGN KEY'
       AND kcu.column_name = 'forecast_id';

    IF fk_name IS NOT NULL THEN
        -- Drop the old CASCADE FK
        EXECUTE format(
            'ALTER TABLE public.forecast_evaluations DROP CONSTRAINT %I',
            fk_name
        );
        -- Recreate with SET NULL
        EXECUTE '
            ALTER TABLE public.forecast_evaluations
            ADD CONSTRAINT forecast_evaluations_forecast_id_fkey
            FOREIGN KEY (forecast_id)
            REFERENCES public.ml_forecasts(id)
            ON DELETE SET NULL
        ';
    END IF;
END $$;
