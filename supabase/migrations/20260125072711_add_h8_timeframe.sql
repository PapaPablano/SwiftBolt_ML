-- Add h8 (8-hour) timeframe to the timeframe enum
-- This supports the new intraday forecast upgrade with 5 horizons: 15m, 1h, 4h, 8h, 1D

-- Add h8 to the timeframe enum type
ALTER TYPE timeframe ADD VALUE 'h8' AFTER 'd1';

-- Verify the enum now includes h8
-- SELECT enum_range(NULL::timeframe) AS all_timeframes;
-- Expected output: {m15,h1,h4,d1,h8,w1}
