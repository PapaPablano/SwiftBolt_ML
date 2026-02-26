-- Fix FK constraint for demo mode
ALTER TABLE strategy_user_strategies DROP CONSTRAINT IF EXISTS strategy_user_strategies_user_id_fkey;
ALTER TABLE strategy_user_strategies ALTER COLUMN user_id DROP NOT NULL;
