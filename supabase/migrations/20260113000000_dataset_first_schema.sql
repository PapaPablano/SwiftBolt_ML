CREATE TABLE IF NOT EXISTS ingestion_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider TEXT NOT NULL DEFAULT 'alpaca',
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
  git_sha TEXT,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bar_datasets (
  dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol_id UUID NOT NULL REFERENCES symbols(id) ON DELETE CASCADE,
  timeframe TEXT NOT NULL CHECK (timeframe IN ('m15', 'h1', 'h4', 'd1', 'w1')),
  provider TEXT NOT NULL DEFAULT 'alpaca',
  start_ts TIMESTAMPTZ NOT NULL,
  end_ts TIMESTAMPTZ NOT NULL,
  as_of_ts TIMESTAMPTZ NOT NULL,
  bar_count INTEGER NOT NULL,
  checksum TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'verified', 'frozen')),
  ingestion_run_id UUID REFERENCES ingestion_runs(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (symbol_id, timeframe, provider, as_of_ts)
);

CREATE INDEX IF NOT EXISTS idx_bar_datasets_symbol_tf_asof
  ON bar_datasets(symbol_id, timeframe, as_of_ts DESC);

CREATE INDEX IF NOT EXISTS idx_bar_datasets_status_asof
  ON bar_datasets(status, as_of_ts DESC);

CREATE TABLE IF NOT EXISTS feature_sets (
  feature_set_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES bar_datasets(dataset_id) ON DELETE CASCADE,
  definition_version TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'building' CHECK (status IN ('building', 'ready', 'failed')),
  feature_keys TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, definition_version)
);

CREATE INDEX IF NOT EXISTS idx_feature_sets_dataset_created
  ON feature_sets(dataset_id, created_at DESC);

CREATE TABLE IF NOT EXISTS feature_rows (
  id BIGSERIAL PRIMARY KEY,
  feature_set_id UUID NOT NULL REFERENCES feature_sets(feature_set_id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL,
  open NUMERIC,
  high NUMERIC,
  low NUMERIC,
  close NUMERIC,
  volume BIGINT,
  features JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (feature_set_id, ts)
);

CREATE INDEX IF NOT EXISTS idx_feature_rows_feature_set_ts
  ON feature_rows(feature_set_id, ts);

CREATE TABLE IF NOT EXISTS forecast_runs (
  forecast_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_id UUID NOT NULL REFERENCES bar_datasets(dataset_id) ON DELETE CASCADE,
  feature_set_id UUID REFERENCES feature_sets(feature_set_id) ON DELETE SET NULL,
  model_key TEXT NOT NULL,
  model_version TEXT NOT NULL,
  horizon TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
  metrics JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_dataset_created
  ON forecast_runs(dataset_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_runs_feature_set_created
  ON forecast_runs(feature_set_id, created_at DESC);

CREATE TABLE IF NOT EXISTS forecast_points (
  id BIGSERIAL PRIMARY KEY,
  forecast_run_id UUID NOT NULL REFERENCES forecast_runs(forecast_run_id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL,
  yhat NUMERIC NOT NULL,
  lower NUMERIC,
  upper NUMERIC,
  confidence NUMERIC,
  kind TEXT NOT NULL DEFAULT 'point' CHECK (kind IN ('point', 'path')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (forecast_run_id, ts, kind)
);

CREATE INDEX IF NOT EXISTS idx_forecast_points_run_ts
  ON forecast_points(forecast_run_id, ts);

CREATE OR REPLACE FUNCTION update_feature_sets_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS feature_sets_updated_at_trigger ON feature_sets;
CREATE TRIGGER feature_sets_updated_at_trigger
  BEFORE UPDATE ON feature_sets
  FOR EACH ROW
  EXECUTE FUNCTION update_feature_sets_updated_at();

ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE bar_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_points ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Service role can manage ingestion_runs" ON ingestion_runs;
CREATE POLICY "Service role can manage ingestion_runs"
  ON ingestion_runs FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage bar_datasets" ON bar_datasets;
CREATE POLICY "Service role can manage bar_datasets"
  ON bar_datasets FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage feature_sets" ON feature_sets;
CREATE POLICY "Service role can manage feature_sets"
  ON feature_sets FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage feature_rows" ON feature_rows;
CREATE POLICY "Service role can manage feature_rows"
  ON feature_rows FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage forecast_runs" ON forecast_runs;
CREATE POLICY "Service role can manage forecast_runs"
  ON forecast_runs FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage forecast_points" ON forecast_points;
CREATE POLICY "Service role can manage forecast_points"
  ON forecast_points FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "Authenticated users can read ingestion_runs" ON ingestion_runs;
CREATE POLICY "Authenticated users can read ingestion_runs"
  ON ingestion_runs FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read bar_datasets" ON bar_datasets;
CREATE POLICY "Authenticated users can read bar_datasets"
  ON bar_datasets FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read feature_sets" ON feature_sets;
CREATE POLICY "Authenticated users can read feature_sets"
  ON feature_sets FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read feature_rows" ON feature_rows;
CREATE POLICY "Authenticated users can read feature_rows"
  ON feature_rows FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read forecast_runs" ON forecast_runs;
CREATE POLICY "Authenticated users can read forecast_runs"
  ON forecast_runs FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS "Authenticated users can read forecast_points" ON forecast_points;
CREATE POLICY "Authenticated users can read forecast_points"
  ON forecast_points FOR SELECT TO authenticated USING (true);

GRANT SELECT ON ingestion_runs TO authenticated;
GRANT SELECT ON bar_datasets TO authenticated;
GRANT SELECT ON feature_sets TO authenticated;
GRANT SELECT ON feature_rows TO authenticated;
GRANT SELECT ON forecast_runs TO authenticated;
GRANT SELECT ON forecast_points TO authenticated;

GRANT ALL ON ingestion_runs TO service_role;
GRANT ALL ON bar_datasets TO service_role;
GRANT ALL ON feature_sets TO service_role;
GRANT ALL ON feature_rows TO service_role;
GRANT ALL ON forecast_runs TO service_role;
GRANT ALL ON forecast_points TO service_role;

GRANT USAGE, SELECT ON SEQUENCE feature_rows_id_seq TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE forecast_points_id_seq TO authenticated;
GRANT USAGE, SELECT ON SEQUENCE feature_rows_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE forecast_points_id_seq TO service_role;
