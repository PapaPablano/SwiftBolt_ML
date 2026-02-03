-- Alpaca 4h OHLC clone for ML experiments (TabPFN / hybrid).
-- Used only when timeframe=h4 and source=alpaca_4h; regime analysis stays on d1 from ohlc_bars_v2.

CREATE TABLE IF NOT EXISTS ohlc_bars_h4_alpaca (
  id BIGSERIAL PRIMARY KEY,
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  ts TIMESTAMP NOT NULL,
  open DECIMAL(10, 4),
  high DECIMAL(10, 4),
  low DECIMAL(10, 4),
  close DECIMAL(10, 4),
  volume BIGINT,
  provider VARCHAR(20) NOT NULL DEFAULT 'alpaca',
  created_at TIMESTAMP DEFAULT now(),
  UNIQUE(symbol_id, ts)
);

CREATE INDEX idx_ohlc_h4_alpaca_symbol_ts ON ohlc_bars_h4_alpaca(symbol_id, ts DESC);

COMMENT ON TABLE ohlc_bars_h4_alpaca IS '4h bars from Alpaca for TabPFN/hybrid ML experiments; same feature pipeline as ohlc_bars_v2';

GRANT SELECT, INSERT, UPDATE ON ohlc_bars_h4_alpaca TO authenticated;
GRANT SELECT, INSERT, UPDATE ON ohlc_bars_h4_alpaca TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ohlc_bars_h4_alpaca_id_seq TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE ohlc_bars_h4_alpaca_id_seq TO service_role;
