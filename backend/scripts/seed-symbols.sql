-- Seed script: Inserts sample symbols into the database
-- Usage: psql -f seed-symbols.sql OR run via Supabase SQL Editor
-- Safe to run multiple times (uses ON CONFLICT DO NOTHING)

-- ============================================================================
-- STOCKS (10 symbols)
-- ============================================================================

INSERT INTO symbols (ticker, asset_type, description, primary_source)
VALUES
  ('AAPL', 'stock', 'Apple Inc. - Consumer electronics, software, and services', 'finnhub'),
  ('MSFT', 'stock', 'Microsoft Corporation - Software, cloud computing, and hardware', 'finnhub'),
  ('GOOGL', 'stock', 'Alphabet Inc. Class A - Search, advertising, and cloud services', 'finnhub'),
  ('AMZN', 'stock', 'Amazon.com Inc. - E-commerce, cloud computing, and AI', 'finnhub'),
  ('TSLA', 'stock', 'Tesla Inc. - Electric vehicles and clean energy', 'finnhub'),
  ('NVDA', 'stock', 'NVIDIA Corporation - Graphics processing and AI computing', 'finnhub'),
  ('META', 'stock', 'Meta Platforms Inc. - Social media and virtual reality', 'finnhub'),
  ('CRWD', 'stock', 'CrowdStrike Holdings, Inc. - Cybersecurity technology', 'finnhub'),
  ('JPM', 'stock', 'JPMorgan Chase & Co. - Global financial services and banking', 'finnhub'),
  ('V', 'stock', 'Visa Inc. - Global payments technology', 'finnhub'),
  ('WMT', 'stock', 'Walmart Inc. - Multinational retail corporation', 'finnhub')
ON CONFLICT (ticker) DO NOTHING;

-- ============================================================================
-- FUTURES (5 symbols)
-- ============================================================================

INSERT INTO symbols (ticker, asset_type, description, primary_source)
VALUES
  ('ES', 'future', 'E-mini S&P 500 Futures - CME equity index futures', 'massive'),
  ('NQ', 'future', 'E-mini NASDAQ-100 Futures - CME tech-weighted index futures', 'massive'),
  ('CL', 'future', 'Crude Oil WTI Futures - NYMEX energy futures', 'massive'),
  ('GC', 'future', 'Gold Futures - COMEX precious metals futures', 'massive'),
  ('ZB', 'future', 'U.S. Treasury Bond Futures - CBOT 30-year bond futures', 'massive')
ON CONFLICT (ticker) DO NOTHING;

-- ============================================================================
-- OPTIONS-READY UNDERLYINGS (5 ETFs/Indexes)
-- ============================================================================

INSERT INTO symbols (ticker, asset_type, description, primary_source)
VALUES
  ('SPY', 'stock', 'SPDR S&P 500 ETF Trust - Tracks the S&P 500 index', 'finnhub'),
  ('QQQ', 'stock', 'Invesco QQQ Trust - Tracks the NASDAQ-100 index', 'finnhub'),
  ('IWM', 'stock', 'iShares Russell 2000 ETF - Tracks small-cap stocks', 'finnhub'),
  ('DIA', 'stock', 'SPDR Dow Jones Industrial Average ETF - Tracks the DJIA', 'finnhub'),
  ('VIX', 'stock', 'CBOE Volatility Index - Market volatility gauge', 'finnhub')
ON CONFLICT (ticker) DO NOTHING;

-- ============================================================================
-- Verification query (optional - uncomment to check results)
-- ============================================================================

-- SELECT ticker, asset_type, description FROM symbols ORDER BY asset_type, ticker;
