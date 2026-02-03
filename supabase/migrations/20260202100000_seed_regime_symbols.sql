-- Seed symbols used by regime/TabPFN 4h backfill (PG, KO, MRK, AMGN, BRK.B, ALB).
-- Backfill fails with "0 rows" for get_symbol_id when these are missing from symbols.
-- Idempotent: ON CONFLICT DO NOTHING.

INSERT INTO symbols (ticker, asset_type, primary_source, description)
VALUES
  ('PG',   'stock'::asset_type, 'alpaca'::data_provider, 'Procter & Gamble'),
  ('KO',   'stock'::asset_type, 'alpaca'::data_provider, 'Coca-Cola'),
  ('MRK',  'stock'::asset_type, 'alpaca'::data_provider, 'Merck'),
  ('AMGN', 'stock'::asset_type, 'alpaca'::data_provider, 'Amgen'),
  ('BRK.B','stock'::asset_type, 'alpaca'::data_provider, 'Berkshire Hathaway Class B'),
  ('ALB',  'stock'::asset_type, 'alpaca'::data_provider, 'Albemarle')
ON CONFLICT (ticker) DO NOTHING;
