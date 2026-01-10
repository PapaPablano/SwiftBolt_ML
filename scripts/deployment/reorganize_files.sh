#!/bin/bash
# Reorganize scattered files into proper directories
# Run from project root: ./reorganize_files.sh

set -e  # Exit on error

echo "🗂️  Starting file reorganization..."

# Architecture Documentation → docs/architecture/
echo "📐 Moving architecture docs..."
mv -n DATA_FLOW_MIGRATION_PLAN.md docs/architecture/ 2>/dev/null || true
mv -n DATA_LAYER_SEPARATION_IMPLEMENTATION.md docs/architecture/ 2>/dev/null || true
mv -n EDGE_FUNCTION_STANDARDIZATION.md docs/architecture/ 2>/dev/null || true
mv -n ML_BLUEPRINT_OPTIONS.md docs/architecture/ 2>/dev/null || true
mv -n ML_BLUEPRINT_STOCKS.md docs/architecture/ 2>/dev/null || true

# Deployment Guides → docs/deployment/
echo "🚀 Moving deployment docs..."
mv -n DEPLOYMENT_INSTRUCTIONS.md docs/deployment/ 2>/dev/null || true
mv -n ALPACA_MARKET_INTELLIGENCE_DEPLOYMENT.md docs/deployment/ 2>/dev/null || true
mv -n MARKET_INTELLIGENCE_DEPLOYMENT_COMPLETE.md docs/deployment/ 2>/dev/null || true
mv -n GITHUB_ACTIONS_SETUP.md docs/deployment/ 2>/dev/null || true
mv -n PHASE2_DEPLOYMENT_GUIDE.md docs/deployment/ 2>/dev/null || true
mv -n SPEC8_BACKFILL_DEPLOYMENT_GUIDE.md docs/deployment/ 2>/dev/null || true
mv -n SPEC8_DEPLOYMENT_SUCCESS.md docs/deployment/ 2>/dev/null || true
mv -n RESAMPLING_DEPLOYMENT_GUIDE.md docs/deployment/ 2>/dev/null || true
mv -n FREE_BACKFILL_AUTOMATION_GUIDE.md docs/deployment/ 2>/dev/null || true

# Migration Documentation → docs/migration/
echo "🔄 Moving migration docs..."
mv -n ALPACA_DEPLOYMENT_FIX.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_FIX_CHECKLIST.txt docs/migration/ 2>/dev/null || true
mv -n ALPACA_FIX_PLAN.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_FIX_SUMMARY.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_INTEGRATION_COMPLETE.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_INTEGRATION_SUMMARY.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_MIGRATION_SUMMARY.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_OPTIMIZATION_SUMMARY.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_PROVIDER_STRATEGY.md docs/migration/ 2>/dev/null || true
mv -n ALPACA_REQUIREMENTS_CHECKLIST.md docs/migration/ 2>/dev/null || true
mv -n MIGRATION_POLYGON_TO_YFINANCE.md docs/migration/ 2>/dev/null || true
mv -n EXECUTE_ALPACA_FIX.md docs/migration/ 2>/dev/null || true

# Feature Implementation → docs/features/
echo "✨ Moving feature docs..."
mv -n AUTOMATED_BACKFILL_SUCCESS.md docs/features/ 2>/dev/null || true
mv -n BACKFILL_SETUP.md docs/features/ 2>/dev/null || true
mv -n BACKFILL_SETUP_COMPLETE.md docs/features/ 2>/dev/null || true
mv -n BATCH_DATA_FLOW.md docs/features/ 2>/dev/null || true
mv -n BATCH_FINAL_STATUS.md docs/features/ 2>/dev/null || true
mv -n BATCH_REPAIR_COMPLETE.md docs/features/ 2>/dev/null || true
mv -n BATCH_REPAIR_GUIDE.md docs/features/ 2>/dev/null || true
mv -n BATCH_ROOT_CAUSE_AND_SOLUTION.md docs/features/ 2>/dev/null || true
mv -n BATCH_STATUS_CURRENT.md docs/features/ 2>/dev/null || true
mv -n BATCH_SYSTEM_BLOCKER.md docs/features/ 2>/dev/null || true
mv -n BATCH_SYSTEM_FINAL_SUMMARY.md docs/features/ 2>/dev/null || true
mv -n CLIENT_UI_INTEGRATION_COMPLETE.md docs/features/ 2>/dev/null || true
mv -n HYDRATION_FIX_SUMMARY.md docs/features/ 2>/dev/null || true
mv -n HYDRATION_SYSTEM_STATUS.md docs/features/ 2>/dev/null || true
mv -n INTRADAY_BACKFILL_FIX.md docs/features/ 2>/dev/null || true
mv -n INTRADAY_BACKFILL_GUIDE.md docs/features/ 2>/dev/null || true
mv -n INTRADAY_FIX_SUMMARY.md docs/features/ 2>/dev/null || true
mv -n LIVE_SYMBOL_SEARCH_FIX.md docs/features/ 2>/dev/null || true
mv -n OPTIONS_RANKER_DETAIL_VIEW.md docs/features/ 2>/dev/null || true
mv -n SUPERTREND_AI_IMPLEMENTATION.md docs/features/ 2>/dev/null || true
mv -n TRADINGVIEW_ALIGNMENT_COMPLETE.md docs/features/ 2>/dev/null || true
mv -n WEBCHART_PHASE1_IMPLEMENTATION.md docs/features/ 2>/dev/null || true
mv -n WEBCHART_QUICKSTART.md docs/features/ 2>/dev/null || true
mv -n WEBCHART_TESTING_GUIDE.md docs/features/ 2>/dev/null || true
mv -n SPEC8_UX_ENHANCEMENTS.md docs/features/ 2>/dev/null || true

# Troubleshooting → docs/troubleshooting/
echo "🔧 Moving troubleshooting docs..."
mv -n CHART_ACCURACY_CHECKLIST.md docs/troubleshooting/ 2>/dev/null || true
mv -n CHART_DATA_TROUBLESHOOTING.md docs/troubleshooting/ 2>/dev/null || true
mv -n CHART_FIXES_SUMMARY.md docs/troubleshooting/ 2>/dev/null || true
mv -n CHART_LOADING_FIXES.md docs/troubleshooting/ 2>/dev/null || true
mv -n CHART_RENDERING_FIX_2026-01-04.md docs/troubleshooting/ 2>/dev/null || true
mv -n CHART_STANDARDS.md docs/troubleshooting/ 2>/dev/null || true
mv -n DATA_ACCURACY_FIX.md docs/troubleshooting/ 2>/dev/null || true
mv -n DATA_COLLECTION_AUDIT.md docs/troubleshooting/ 2>/dev/null || true
mv -n DATA_HEALTH_CHECK.md docs/troubleshooting/ 2>/dev/null || true
mv -n DATA_QUALITY_FIX_2026-01-04.md docs/troubleshooting/ 2>/dev/null || true
mv -n FIXES_SUMMARY.md docs/troubleshooting/ 2>/dev/null || true
mv -n INDICATOR_FIX_2026-01-04.md docs/troubleshooting/ 2>/dev/null || true
mv -n TROUBLESHOOTING_WORKFLOW_ERRORS.md docs/troubleshooting/ 2>/dev/null || true
mv -n MISSING_MODEL_FILES.md docs/troubleshooting/ 2>/dev/null || true
mv -n POLYGON_RATE_LIMIT_OPTIMIZATION.md docs/troubleshooting/ 2>/dev/null || true

# Quick Start Guides → docs/
echo "📖 Moving quick start guides..."
mv -n QUICKSTART_BACKFILL.md docs/ 2>/dev/null || true
mv -n QUICKSTART_RANKING_JOBS.md docs/ 2>/dev/null || true
mv -n QUICK_START_CHECKLIST.md docs/ 2>/dev/null || true
mv -n QUICK_START_DATA_SEPARATION.md docs/ 2>/dev/null || true
mv -n README_BACKFILL.md docs/ 2>/dev/null || true
mv -n WATCHLIST_BACKFILL.md docs/ 2>/dev/null || true
mv -n WATCHLIST_RELOAD_GUIDE.md docs/ 2>/dev/null || true

# Project Management → docs/archived/
echo "📦 Archiving project management docs..."
mv -n BUILD_SUCCESS_SUMMARY.md docs/archived/ 2>/dev/null || true
mv -n COMMIT_MESSAGE.md docs/archived/ 2>/dev/null || true
mv -n FINAL_SUMMARY.md docs/archived/ 2>/dev/null || true
mv -n IMPLEMENTATION_SUMMARY.md docs/archived/ 2>/dev/null || true
mv -n PHASE2_BATCH_BACKFILL_GUIDE.md docs/archived/ 2>/dev/null || true
mv -n "PHASE6.5_COMPLETION_SUMMARY.md" docs/archived/ 2>/dev/null || true
mv -n PHASE6_COMPLETION_SUMMARY.md docs/archived/ 2>/dev/null || true
mv -n COST_COMPARISON_AND_RECOMMENDATION.md docs/archived/ 2>/dev/null || true
mv -n SUPABASE_USAGE_AUDIT.md docs/archived/ 2>/dev/null || true
mv -n SUPABASE_ALPACA_DATABASE_UPDATES.md docs/archived/ 2>/dev/null || true
mv -n SCHEMA_REFRESH_INSTRUCTIONS.md docs/archived/ 2>/dev/null || true
mv -n CONFIGURE_PGCRON.md docs/archived/ 2>/dev/null || true

# Xcode Scripts → scripts/xcode/
echo "🍎 Moving Xcode scripts..."
mv -n add_chartdatav2_to_xcode.py scripts/xcode/ 2>/dev/null || true
mv -n add_files_to_xcode.py scripts/xcode/ 2>/dev/null || true
mv -n add_files_to_xcode_simple.sh scripts/xcode/ 2>/dev/null || true
mv -n add_mlreportcard_to_xcode.sh scripts/xcode/ 2>/dev/null || true
mv -n add_new_files_to_xcode.sh scripts/xcode/ 2>/dev/null || true
mv -n add_timeframe_to_xcode.py scripts/xcode/ 2>/dev/null || true
mv -n add_webchart_files.sh scripts/xcode/ 2>/dev/null || true
mv -n add_webchart_to_xcode.py scripts/xcode/ 2>/dev/null || true
mv -n add_webchartcontrols.py scripts/xcode/ 2>/dev/null || true
mv -n ADD_FILES_TO_XCODE.md scripts/xcode/ 2>/dev/null || true
mv -n XCODE_PROJECT_UPDATED.md scripts/xcode/ 2>/dev/null || true

# Database Scripts → scripts/database/
echo "🗄️  Moving database scripts..."
mv -n APPLY_CRITICAL_FIXES.sql scripts/database/ 2>/dev/null || true
mv -n CLEANUP_DUPLICATES.sql scripts/database/ 2>/dev/null || true
mv -n DELETE_CORRUPTED_BARS.sql scripts/database/ 2>/dev/null || true
mv -n FIX_BAD_POLYGON_DATA.sql scripts/database/ 2>/dev/null || true
mv -n RUN_CLEANUP_NOW.sql scripts/database/ 2>/dev/null || true
mv -n check-aapl-data.sql scripts/database/ 2>/dev/null || true
mv -n check-aapl-timeline.sql scripts/database/ 2>/dev/null || true
mv -n check-constraints.sql scripts/database/ 2>/dev/null || true
mv -n check-data-health.sql scripts/database/ 2>/dev/null || true
mv -n deploy_market_intelligence.sql scripts/database/ 2>/dev/null || true
mv -n diagnose-data-gap.sql scripts/database/ 2>/dev/null || true
mv -n fix-aapl-data.sql scripts/database/ 2>/dev/null || true
mv -n full-diagnostic.sql scripts/database/ 2>/dev/null || true
mv -n setup-backfill-cron.sql scripts/database/ 2>/dev/null || true

# Validation Scripts → scripts/validation/
echo "✅ Moving validation scripts..."
mv -n check_nvda_prices.py scripts/validation/ 2>/dev/null || true
mv -n compare_tradingview_indicators.py scripts/validation/ 2>/dev/null || true
mv -n debug_nvda_forecast.py scripts/validation/ 2>/dev/null || true
mv -n debug_nvda_swing.py scripts/validation/ 2>/dev/null || true
mv -n diagnose_indicators.py scripts/validation/ 2>/dev/null || true
mv -n test_p0_modules.py scripts/validation/ 2>/dev/null || true
mv -n test_tradingview_alignment.py scripts/validation/ 2>/dev/null || true
mv -n validate_crwd.py scripts/validation/ 2>/dev/null || true
mv -n validate_fixed_indicators.py scripts/validation/ 2>/dev/null || true
mv -n validate_intraday_health.py scripts/validation/ 2>/dev/null || true
mv -n validate_tradingview_data.py scripts/validation/ 2>/dev/null || true
mv -n verify_database_prices.py scripts/validation/ 2>/dev/null || true
mv -n verify_price_accuracy.py scripts/validation/ 2>/dev/null || true

# Analysis Scripts → scripts/analysis/
echo "📊 Moving analysis scripts..."
mv -n earnings_analyzer.py scripts/analysis/ 2>/dev/null || true
mv -n extrinsic_calculator.py scripts/analysis/ 2>/dev/null || true
mv -n pcr_analyzer.py scripts/analysis/ 2>/dev/null || true
mv -n pop_calculator.py scripts/analysis/ 2>/dev/null || true

# Deployment Scripts → scripts/deployment/
echo "🚢 Moving deployment scripts..."
mv -n deploy_migrations.py scripts/deployment/ 2>/dev/null || true
mv -n execute_migration.py scripts/deployment/ 2>/dev/null || true
mv -n purge_and_refetch_data.sh scripts/deployment/ 2>/dev/null || true
mv -n purge_and_refetch_us_stocks.sh scripts/deployment/ 2>/dev/null || true
mv -n quick-health-check.sh scripts/deployment/ 2>/dev/null || true
mv -n quick_verify_db.sh scripts/deployment/ 2>/dev/null || true
mv -n test-backfill-worker.sh scripts/deployment/ 2>/dev/null || true
mv -n test-backfill.sh scripts/deployment/ 2>/dev/null || true
mv -n test-data-health.sh scripts/deployment/ 2>/dev/null || true

# TradingView Indicators → examples/indicators/
echo "📈 Moving indicator examples..."
mv -n "Enhanced Ranker Integration.txt" examples/indicators/ 2>/dev/null || true
mv -n "Pivot Levels [BigBeluga.txt" examples/indicators/ 2>/dev/null || true
mv -n "Support & Resistance Polynomial Regression.txt" examples/indicators/ 2>/dev/null || true
mv -n "Support and Resistance Logistic Regression.txt" examples/indicators/ 2>/dev/null || true
mv -n "USAGE EXAMPLE.txt" examples/indicators/ 2>/dev/null || true

# Internal Notes → docs/archived/
echo "📝 Archiving internal notes..."
mv -n CLAUDE.md docs/archived/ 2>/dev/null || true
mv -n api_handling.md docs/archived/ 2>/dev/null || true
mv -n dataintegrity.md docs/archived/ 2>/dev/null || true
mv -n forecastingprocesses.md docs/archived/ 2>/dev/null || true
mv -n implemtnation.txt docs/archived/ 2>/dev/null || true
mv -n improvement_swiftml.txt docs/archived/ 2>/dev/null || true
mv -n ml_improvement.md docs/archived/ 2>/dev/null || true
mv -n read_me_starhere.md docs/archived/ 2>/dev/null || true
mv -n technicals_and_ml_improvement.md docs/archived/ 2>/dev/null || true
mv -n technicals_ml_improvments.txt docs/archived/ 2>/dev/null || true
mv -n web-chart-subpanel-wiring.md docs/archived/ 2>/dev/null || true
mv -n web-chart-tooltip-review.md docs/archived/ 2>/dev/null || true

echo ""
echo "✅ File reorganization complete!"
echo ""
echo "📁 New structure:"
echo "  docs/architecture/     - System architecture docs"
echo "  docs/deployment/       - Deployment guides"
echo "  docs/migration/        - Migration documentation"
echo "  docs/features/         - Feature implementation"
echo "  docs/troubleshooting/  - Debug and fix guides"
echo "  docs/archived/         - Old documentation"
echo "  scripts/xcode/         - Xcode project scripts"
echo "  scripts/database/      - SQL scripts"
echo "  scripts/validation/    - Validation scripts"
echo "  scripts/analysis/      - Analysis tools"
echo "  scripts/deployment/    - Deployment scripts"
echo "  examples/indicators/   - TradingView indicators"
echo ""
echo "🧹 Remaining files in root:"
ls -1 *.md *.txt *.py *.sh *.sql 2>/dev/null | grep -v "README.md\|CHANGELOG.md\|CONTRIBUTING.md\|PROJECT_" || echo "  (none - all organized!)"
