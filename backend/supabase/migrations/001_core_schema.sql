-- ============================================================================
-- SwiftBolt ML - Core Database Schema
-- Migration: 001_core_schema.sql
-- ============================================================================

-- Note: gen_random_uuid() is built into PostgreSQL 13+ (no extension needed)

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE asset_type AS ENUM ('stock', 'future', 'option', 'crypto');
CREATE TYPE data_provider AS ENUM ('finnhub', 'massive');
CREATE TYPE timeframe AS ENUM ('m15', 'h1', 'h4', 'd1', 'w1');
CREATE TYPE trend_label AS ENUM ('bullish', 'neutral', 'bearish');
CREATE TYPE option_side AS ENUM ('call', 'put');

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- -----------------------------------------------------------------------------
-- symbols: Master list of tradeable instruments
-- -----------------------------------------------------------------------------
CREATE TABLE symbols (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker TEXT NOT NULL UNIQUE,
    asset_type asset_type NOT NULL,
    description TEXT,
    primary_source data_provider NOT NULL DEFAULT 'finnhub',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_symbols_ticker ON symbols(ticker);
CREATE INDEX idx_symbols_asset_type ON symbols(asset_type);

-- -----------------------------------------------------------------------------
-- ohlc_bars: Historical OHLCV price data
-- -----------------------------------------------------------------------------
CREATE TABLE ohlc_bars (
    id BIGSERIAL PRIMARY KEY,
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    timeframe timeframe NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(20, 6) NOT NULL,
    high NUMERIC(20, 6) NOT NULL,
    low NUMERIC(20, 6) NOT NULL,
    close NUMERIC(20, 6) NOT NULL,
    volume NUMERIC(20, 2) NOT NULL DEFAULT 0,
    provider data_provider NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique constraint to prevent duplicate bars
CREATE UNIQUE INDEX idx_ohlc_bars_unique ON ohlc_bars(symbol_id, timeframe, ts);
CREATE INDEX idx_ohlc_bars_symbol_timeframe ON ohlc_bars(symbol_id, timeframe);
CREATE INDEX idx_ohlc_bars_ts ON ohlc_bars(ts DESC);

-- -----------------------------------------------------------------------------
-- quotes: Latest quote data for symbols
-- -----------------------------------------------------------------------------
CREATE TABLE quotes (
    symbol_id UUID PRIMARY KEY REFERENCES symbols(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    last NUMERIC(20, 6),
    bid NUMERIC(20, 6),
    ask NUMERIC(20, 6),
    day_high NUMERIC(20, 6),
    day_low NUMERIC(20, 6),
    prev_close NUMERIC(20, 6),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_quotes_ts ON quotes(ts DESC);

-- -----------------------------------------------------------------------------
-- ml_forecasts: ML model predictions
-- -----------------------------------------------------------------------------
CREATE TABLE ml_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    horizon TEXT NOT NULL, -- e.g., '1D', '1W', '1M'
    overall_label trend_label NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    points JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- points schema: [{ "ts": "ISO8601", "value": number, "lower": number?, "upper": number? }]
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ml_forecasts_symbol ON ml_forecasts(symbol_id);
CREATE INDEX idx_ml_forecasts_symbol_horizon ON ml_forecasts(symbol_id, horizon);
CREATE INDEX idx_ml_forecasts_run_at ON ml_forecasts(run_at DESC);

-- -----------------------------------------------------------------------------
-- options_ranks: ML-scored options contracts
-- -----------------------------------------------------------------------------
CREATE TABLE options_ranks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    underlying_symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    expiry DATE NOT NULL,
    strike NUMERIC(20, 6) NOT NULL,
    side option_side NOT NULL,
    ml_score NUMERIC(5, 4) CHECK (ml_score >= 0 AND ml_score <= 1),
    implied_vol NUMERIC(10, 6),
    delta NUMERIC(10, 6),
    gamma NUMERIC(10, 6),
    open_interest INTEGER DEFAULT 0,
    volume INTEGER DEFAULT 0,
    run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_options_ranks_underlying ON options_ranks(underlying_symbol_id);
CREATE INDEX idx_options_ranks_expiry ON options_ranks(expiry);
CREATE INDEX idx_options_ranks_ml_score ON options_ranks(ml_score DESC);
CREATE UNIQUE INDEX idx_options_ranks_unique ON options_ranks(underlying_symbol_id, expiry, strike, side);

-- -----------------------------------------------------------------------------
-- watchlists: User watchlists
-- -----------------------------------------------------------------------------
CREATE TABLE watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_watchlists_user ON watchlists(user_id);

-- -----------------------------------------------------------------------------
-- watchlist_items: Symbols in watchlists
-- -----------------------------------------------------------------------------
CREATE TABLE watchlist_items (
    watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (watchlist_id, symbol_id)
);

CREATE INDEX idx_watchlist_items_symbol ON watchlist_items(symbol_id);

-- -----------------------------------------------------------------------------
-- scanner_alerts: Triggered scanner conditions
-- -----------------------------------------------------------------------------
CREATE TABLE scanner_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    user_id UUID, -- nullable for system-wide alerts
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    condition_label TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info', -- 'info', 'warning', 'critical'
    dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scanner_alerts_symbol ON scanner_alerts(symbol_id);
CREATE INDEX idx_scanner_alerts_user ON scanner_alerts(user_id);
CREATE INDEX idx_scanner_alerts_triggered ON scanner_alerts(triggered_at DESC);

-- -----------------------------------------------------------------------------
-- news_items: Cached news articles
-- -----------------------------------------------------------------------------
CREATE TABLE news_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID REFERENCES symbols(id) ON DELETE SET NULL, -- nullable for market-wide news
    title TEXT NOT NULL,
    source TEXT,
    url TEXT,
    summary TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_items_symbol ON news_items(symbol_id);
CREATE INDEX idx_news_items_published ON news_items(published_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE symbols ENABLE ROW LEVEL SECURITY;
ALTER TABLE ohlc_bars ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE options_ranks ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE scanner_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE news_items ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- Public read access for market data (symbols, ohlc, quotes, news)
-- These are not user-specific, so all authenticated users can read
-- -----------------------------------------------------------------------------

-- symbols: all authenticated users can read
CREATE POLICY "symbols_select_authenticated" ON symbols
    FOR SELECT TO authenticated
    USING (true);

-- ohlc_bars: all authenticated users can read
CREATE POLICY "ohlc_bars_select_authenticated" ON ohlc_bars
    FOR SELECT TO authenticated
    USING (true);

-- quotes: all authenticated users can read
CREATE POLICY "quotes_select_authenticated" ON quotes
    FOR SELECT TO authenticated
    USING (true);

-- ml_forecasts: all authenticated users can read
CREATE POLICY "ml_forecasts_select_authenticated" ON ml_forecasts
    FOR SELECT TO authenticated
    USING (true);

-- options_ranks: all authenticated users can read
CREATE POLICY "options_ranks_select_authenticated" ON options_ranks
    FOR SELECT TO authenticated
    USING (true);

-- news_items: all authenticated users can read
CREATE POLICY "news_items_select_authenticated" ON news_items
    FOR SELECT TO authenticated
    USING (true);

-- -----------------------------------------------------------------------------
-- User-owned data (watchlists, scanner_alerts)
-- Users can only access their own data
-- -----------------------------------------------------------------------------

-- watchlists: users can CRUD their own watchlists
CREATE POLICY "watchlists_select_own" ON watchlists
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "watchlists_insert_own" ON watchlists
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "watchlists_update_own" ON watchlists
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "watchlists_delete_own" ON watchlists
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

-- watchlist_items: users can CRUD items in their own watchlists
CREATE POLICY "watchlist_items_select_own" ON watchlist_items
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM watchlists w
            WHERE w.id = watchlist_items.watchlist_id
            AND w.user_id = auth.uid()
        )
    );

CREATE POLICY "watchlist_items_insert_own" ON watchlist_items
    FOR INSERT TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM watchlists w
            WHERE w.id = watchlist_items.watchlist_id
            AND w.user_id = auth.uid()
        )
    );

CREATE POLICY "watchlist_items_delete_own" ON watchlist_items
    FOR DELETE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM watchlists w
            WHERE w.id = watchlist_items.watchlist_id
            AND w.user_id = auth.uid()
        )
    );

-- scanner_alerts: users can read/dismiss their own alerts
CREATE POLICY "scanner_alerts_select_own" ON scanner_alerts
    FOR SELECT TO authenticated
    USING (user_id IS NULL OR auth.uid() = user_id);

CREATE POLICY "scanner_alerts_update_own" ON scanner_alerts
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- -----------------------------------------------------------------------------
-- Service role has full access (for Edge Functions and ML jobs)
-- -----------------------------------------------------------------------------

-- symbols: service role can insert/update
CREATE POLICY "symbols_service_all" ON symbols
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- ohlc_bars: service role can insert/update
CREATE POLICY "ohlc_bars_service_all" ON ohlc_bars
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- quotes: service role can insert/update
CREATE POLICY "quotes_service_all" ON quotes
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- ml_forecasts: service role can insert/update
CREATE POLICY "ml_forecasts_service_all" ON ml_forecasts
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- options_ranks: service role can insert/update
CREATE POLICY "options_ranks_service_all" ON options_ranks
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- news_items: service role can insert/update
CREATE POLICY "news_items_service_all" ON news_items
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- scanner_alerts: service role can insert
CREATE POLICY "scanner_alerts_service_all" ON scanner_alerts
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER update_symbols_updated_at
    BEFORE UPDATE ON symbols
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_watchlists_updated_at
    BEFORE UPDATE ON watchlists
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quotes_updated_at
    BEFORE UPDATE ON quotes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE symbols IS 'Master list of tradeable instruments (stocks, futures, options, crypto)';
COMMENT ON TABLE ohlc_bars IS 'Historical OHLCV price data at various timeframes';
COMMENT ON TABLE quotes IS 'Latest quote data for each symbol';
COMMENT ON TABLE ml_forecasts IS 'ML model predictions with forecast points';
COMMENT ON TABLE options_ranks IS 'ML-scored options contracts for the options ranker';
COMMENT ON TABLE watchlists IS 'User-created watchlists';
COMMENT ON TABLE watchlist_items IS 'Symbols contained in watchlists';
COMMENT ON TABLE scanner_alerts IS 'Triggered scanner conditions and alerts';
COMMENT ON TABLE news_items IS 'Cached news articles from providers';
