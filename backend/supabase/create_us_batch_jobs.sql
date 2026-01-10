-- Create US-Only Batch Job Definitions
-- Replaces international symbol batches with US symbols supported by Alpaca

-- Step 1: Cancel all existing batch job runs
UPDATE job_runs
SET status = 'cancelled',
    updated_at = now()
WHERE job_def_id IN (
  SELECT id FROM job_definitions 
  WHERE symbols_array IS NOT NULL
)
AND status IN ('queued', 'running');

-- Step 2: Disable existing batch job definitions
UPDATE job_definitions
SET enabled = false,
    updated_at = now()
WHERE symbols_array IS NOT NULL;

-- Step 3: Create new US-only batch job definitions
-- 61 US symbols divided into batches of 50 (Alpaca limit) = 2 batches

-- Batch 1: 50 symbols
INSERT INTO job_definitions (
  job_type,
  symbol,
  timeframe,
  window_days,
  priority,
  enabled,
  symbols_array,
  batch_number,
  total_batches
) VALUES
  ('fetch_historical', 'US_BATCH_1', 'h1', 365, 100, true,
   '["A","AA","AAPL","ABTC","ACN","AI","AMAT","AMD","AMZN","APP","AVGO","AXP","BHAT","BIT","BMNR","BRK.A","BTDR","CRWD","DIA","DIS","DKS","FICO","GBTC","GOOG","GOOGL","GSHD","GT","HOOD","IDXX","IWM","JNJ","JPM","LIN","LLY","MA","META","MSFT","MU","NFLX","NVDA","NXPI","ORCL","PL","PLTR","QQQ","RTX","SLB","SMPL","SPY","TJX"]'::jsonb,
   1, 2),
  ('fetch_historical', 'US_BATCH_1', 'm15', 90, 100, true,
   '["A","AA","AAPL","ABTC","ACN","AI","AMAT","AMD","AMZN","APP","AVGO","AXP","BHAT","BIT","BMNR","BRK.A","BTDR","CRWD","DIA","DIS","DKS","FICO","GBTC","GOOG","GOOGL","GSHD","GT","HOOD","IDXX","IWM","JNJ","JPM","LIN","LLY","MA","META","MSFT","MU","NFLX","NVDA","NXPI","ORCL","PL","PLTR","QQQ","RTX","SLB","SMPL","SPY","TJX"]'::jsonb,
   1, 2),
  ('fetch_historical', 'US_BATCH_1', 'h4', 180, 100, true,
   '["A","AA","AAPL","ABTC","ACN","AI","AMAT","AMD","AMZN","APP","AVGO","AXP","BHAT","BIT","BMNR","BRK.A","BTDR","CRWD","DIA","DIS","DKS","FICO","GBTC","GOOG","GOOGL","GSHD","GT","HOOD","IDXX","IWM","JNJ","JPM","LIN","LLY","MA","META","MSFT","MU","NFLX","NVDA","NXPI","ORCL","PL","PLTR","QQQ","RTX","SLB","SMPL","SPY","TJX"]'::jsonb,
   1, 2),
  ('fetch_historical', 'US_BATCH_1', 'd1', 730, 100, true,
   '["A","AA","AAPL","ABTC","ACN","AI","AMAT","AMD","AMZN","APP","AVGO","AXP","BHAT","BIT","BMNR","BRK.A","BTDR","CRWD","DIA","DIS","DKS","FICO","GBTC","GOOG","GOOGL","GSHD","GT","HOOD","IDXX","IWM","JNJ","JPM","LIN","LLY","MA","META","MSFT","MU","NFLX","NVDA","NXPI","ORCL","PL","PLTR","QQQ","RTX","SLB","SMPL","SPY","TJX"]'::jsonb,
   1, 2);

-- Batch 2: 11 symbols
INSERT INTO job_definitions (
  job_type,
  symbol,
  timeframe,
  window_days,
  priority,
  enabled,
  symbols_array,
  batch_number,
  total_batches
) VALUES
  ('fetch_historical', 'US_BATCH_2', 'h1', 365, 100, true,
   '["TMUS","TSLA","UNH","V","VIX","VOXX","VZ","WMT","XOM","ZBH","ZIM"]'::jsonb,
   2, 2),
  ('fetch_historical', 'US_BATCH_2', 'm15', 90, 100, true,
   '["TMUS","TSLA","UNH","V","VIX","VOXX","VZ","WMT","XOM","ZBH","ZIM"]'::jsonb,
   2, 2),
  ('fetch_historical', 'US_BATCH_2', 'h4', 180, 100, true,
   '["TMUS","TSLA","UNH","V","VIX","VOXX","VZ","WMT","XOM","ZBH","ZIM"]'::jsonb,
   2, 2),
  ('fetch_historical', 'US_BATCH_2', 'd1', 730, 100, true,
   '["TMUS","TSLA","UNH","V","VIX","VOXX","VZ","WMT","XOM","ZBH","ZIM"]'::jsonb,
   2, 2);

-- Step 4: Verify new batch job definitions
SELECT 
  symbol,
  timeframe,
  jsonb_array_length(symbols_array) as symbol_count,
  batch_number,
  total_batches,
  enabled
FROM job_definitions
WHERE symbols_array IS NOT NULL
  AND enabled = true
ORDER BY timeframe, batch_number;
