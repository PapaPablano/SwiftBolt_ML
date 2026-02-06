-- sentiment_scores: daily aggregate sentiment per symbol for backtest/features
-- Populated by backfill script (Alpaca/FinViz + VADER). ML pipeline reads via get_historical_sentiment_series.

CREATE TABLE IF NOT EXISTS sentiment_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
    as_of_date DATE NOT NULL,
    sentiment_score REAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(symbol_id, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_sentiment_scores_symbol_date ON sentiment_scores(symbol_id, as_of_date DESC);
COMMENT ON TABLE sentiment_scores IS 'Daily aggregate news sentiment (VADER) per symbol for ML backtest and features';

-- Optional: allow storing per-article sentiment when news is cached/backfilled
ALTER TABLE news_items ADD COLUMN IF NOT EXISTS sentiment_score REAL;
