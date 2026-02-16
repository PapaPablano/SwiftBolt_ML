-- ============================================================================
-- Seed MVP Futures Roots (Fix)
-- Migration: 20260216020000_seed_futures_roots_fix.sql
-- ============================================================================

INSERT INTO futures_roots (symbol, name, exchange, sector, tick_size, point_value, currency, session_template) VALUES
('ES', 'E-mini S&P 500', 'CME', 'indices', 0.25, 50.00, 'USD', 'CME_US_Index'),
('NQ', 'E-mini NASDAQ-100', 'CME', 'indices', 0.25, 20.00, 'USD', 'CME_US_Index'),
('RTY', 'E-mini Russell 2000', 'CME', 'indices', 0.10, 50.00, 'USD', 'CME_US_Index'),
('YM', 'E-mini Dow ($5)', 'CBOT', 'indices', 1.00, 5.00, 'USD', 'CBOT_Index'),
('EMD', 'E-mini S&P MidCap 400', 'CME', 'indices', 0.10, 100.00, 'USD', 'CME_US_Index'),
('GC', 'Gold', 'COMEX', 'metals', 0.10, 100.00, 'USD', 'COMEX_Metals'),
('SI', 'Silver', 'COMEX', 'metals', 0.005, 5000.00, 'USD', 'COMEX_Metals'),
('HG', 'Copper', 'COMEX', 'metals', 0.0005, 25000.00, 'USD', 'COMEX_Metals')
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO futures_roll_config (root_id, roll_method, adjustment_method, auto_roll_enabled)
SELECT id, 'volume', 'none', TRUE FROM futures_roots
ON CONFLICT (root_id) DO NOTHING;
