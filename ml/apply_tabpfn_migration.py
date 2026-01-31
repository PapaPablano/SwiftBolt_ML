"""
Apply TabPFN database migration without psql.

Uses psycopg2 with DATABASE_URL. Run from ml directory:

    export DATABASE_URL="postgresql://user:pass@host:5432/postgres"   # if not in ml/.env
    python apply_tabpfn_migration.py

Or from repo root:
    export DATABASE_URL="..."
    python ml/apply_tabpfn_migration.py
"""
import os
import sys

# When run as "python apply_tabpfn_migration.py" from ml/, config is ml.config
# When run as "python ml/apply_tabpfn_migration.py" from repo root, we need ml on path
_ml_dir = os.path.dirname(os.path.abspath(__file__))
if _ml_dir not in sys.path:
    sys.path.insert(0, _ml_dir)

try:
    from config.settings import settings
    _database_url = getattr(settings, "database_url", None) or os.environ.get("DATABASE_URL")
except Exception as e:
    _database_url = os.environ.get("DATABASE_URL")
    if not _database_url:
        print("Could not load config:", e)

if not _database_url:
    print("=" * 80)
    print("DATABASE_URL not set. Set it or add to ml/.env")
    print("=" * 80)
    print('  export DATABASE_URL="postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres"')
    print("  python apply_tabpfn_migration.py")
    sys.exit(1)

import psycopg2
from psycopg2.extras import RealDictCursor


def run():
    print("=" * 80)
    print("APPLYING TABPFN MIGRATION: ADD model_type COLUMN")
    print("=" * 80)

    try:
        conn = psycopg2.connect(_database_url)
    except psycopg2.OperationalError as e:
        print(f"\n✗ Could not connect to database: {e}")
        print("  Check DATABASE_URL and network.")
        sys.exit(1)

    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    try:
        # 1. Add model_type column
        print("\n1. Adding model_type column...")
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'ml_forecasts' AND column_name = 'model_type'
        """)
        if cur.fetchone() is None:
            cur.execute("""
                ALTER TABLE ml_forecasts
                ADD COLUMN model_type TEXT DEFAULT 'xgboost'
                CHECK (model_type IN ('xgboost', 'tabpfn', 'transformer', 'baseline', 'arima', 'prophet', 'ensemble'))
            """)
            print("   ✓ Column added")
        else:
            print("   ✓ Column already exists")

        # 2. Update existing records
        print("\n2. Updating existing records...")
        cur.execute("""
            UPDATE ml_forecasts SET model_type = 'xgboost' WHERE model_type IS NULL
        """)
        print(f"   ✓ Updated {cur.rowcount} rows")

        # 3. Indexes
        print("\n3. Creating indexes...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ml_forecasts_model_type
            ON ml_forecasts(model_type, created_at DESC)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_ml_forecasts_symbol_model_type
            ON ml_forecasts(symbol_id, model_type, horizon, created_at DESC)
        """)
        print("   ✓ Indexes created")

        cur.execute("""
            COMMENT ON COLUMN ml_forecasts.model_type IS
            'ML model that generated this forecast: xgboost, tabpfn, transformer, baseline, etc.'
        """)

        # 4. View
        print("\n4. Creating forecast_model_comparison view...")
        cur.execute("""
            CREATE OR REPLACE VIEW forecast_model_comparison AS
            SELECT
                s.ticker as symbol,
                f.horizon,
                f.model_type,
                f.overall_label as direction,
                f.confidence,
                f.forecast_return,
                f.quality_score,
                f.model_agreement,
                f.n_models,
                f.synthesis_data->>'train_time_sec' as train_time_sec,
                f.synthesis_data->>'inference_time_sec' as inference_time_sec,
                f.created_at
            FROM ml_forecasts f
            JOIN symbols s ON f.symbol_id = s.id
            WHERE f.created_at > NOW() - INTERVAL '24 hours'
            ORDER BY s.ticker, f.horizon, f.model_type, f.created_at DESC
        """)
        print("   ✓ View created")

        # 5. Function
        print("\n5. Creating get_model_agreement_stats function...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION get_model_agreement_stats(
                p_symbol_id UUID,
                p_horizon TEXT DEFAULT '1D',
                p_lookback_hours INTEGER DEFAULT 24
            )
            RETURNS TABLE (
                model_type TEXT,
                forecast_count BIGINT,
                avg_confidence NUMERIC,
                bullish_pct NUMERIC,
                bearish_pct NUMERIC,
                neutral_pct NUMERIC,
                avg_forecast_return NUMERIC,
                avg_quality_score NUMERIC
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    f.model_type,
                    COUNT(*)::BIGINT AS forecast_count,
                    AVG(f.confidence)::NUMERIC AS avg_confidence,
                    (SUM(CASE WHEN LOWER(f.overall_label) = 'bullish' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS bullish_pct,
                    (SUM(CASE WHEN LOWER(f.overall_label) = 'bearish' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS bearish_pct,
                    (SUM(CASE WHEN LOWER(f.overall_label) = 'neutral' THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100)::NUMERIC AS neutral_pct,
                    AVG(f.forecast_return)::NUMERIC AS avg_forecast_return,
                    AVG(f.quality_score)::NUMERIC AS avg_quality_score
                FROM ml_forecasts f
                WHERE f.symbol_id = p_symbol_id
                    AND f.horizon = p_horizon
                    AND f.created_at >= NOW() - (p_lookback_hours || ' hours')::INTERVAL
                GROUP BY f.model_type
                ORDER BY f.model_type;
            END;
            $$ LANGUAGE plpgsql;
        """)
        print("   ✓ Function created")

        # 6. Verify
        print("\n6. Verifying migration...")
        cur.execute("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'ml_forecasts' AND column_name = 'model_type'
        """)
        row = cur.fetchone()
        if row:
            print(f"   ✓ model_type column: type={row['data_type']}, default={row['column_default']}")
        else:
            print("   ✗ model_type column not found")
            raise RuntimeError("Migration verification failed")

        # 7. Forecast counts
        print("\n7. Forecast counts by model_type...")
        cur.execute("""
            SELECT model_type, COUNT(*) as count, MAX(created_at) as latest
            FROM ml_forecasts
            GROUP BY model_type
            ORDER BY model_type
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"     - {r['model_type']}: {r['count']} forecasts")
        else:
            print("     ⚠ No forecasts in database yet")

    finally:
        cur.close()
        conn.close()

    print("\n" + "=" * 80)
    print("✓ MIGRATION COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("  1. Test TabPFN: python -m src.unified_forecast_job --symbol AAPL --model-type tabpfn")
    print("  2. Compare models: cd .. && python experiments/tabpfn_vs_xgboost.py --symbols AAPL,MSFT --generate")
    print("  3. View results: SELECT * FROM forecast_model_comparison;")


if __name__ == "__main__":
    run()
