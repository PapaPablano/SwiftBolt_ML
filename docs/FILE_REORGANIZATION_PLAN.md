# 📁 File Reorganization Plan

**Total Files to Organize:** 140+ files in root directory  
**Target:** Clean root with organized subdirectories

---

## 📋 Reorganization Strategy

### Target Folder Structure

```
SwiftBolt_ML/
├── docs/
│   ├── architecture/          # System architecture docs
│   ├── deployment/            # Deployment guides
│   ├── migration/             # Migration documentation
│   ├── features/              # Feature implementation docs
│   ├── troubleshooting/       # Debug and fix guides
│   └── archived/              # Old/completed documentation
│
├── scripts/
│   ├── xcode/                 # Xcode project manipulation
│   ├── database/              # SQL scripts
│   ├── validation/            # Data validation scripts
│   ├── deployment/            # Deployment scripts
│   └── analysis/              # Analysis and debugging
│
├── examples/                  # Example usage
│   └── indicators/            # TradingView indicator examples
│
└── [keep at root]
    ├── README.md
    ├── CHANGELOG.md
    ├── CONTRIBUTING.md
    ├── LICENSE
    ├── pyproject.toml
    ├── .gitignore
    └── .env.example
```

---

## 🗂️ File Categorization

### 1. Architecture Documentation → `docs/architecture/`
- ARCHITECTURE.md (already in docs/)
- DATA_FLOW_MIGRATION_PLAN.md
- DATA_LAYER_SEPARATION_IMPLEMENTATION.md
- EDGE_FUNCTION_STANDARDIZATION.md
- ML_BLUEPRINT_OPTIONS.md
- ML_BLUEPRINT_STOCKS.md

### 2. Deployment Guides → `docs/deployment/`
- DEPLOYMENT_INSTRUCTIONS.md
- ALPACA_MARKET_INTELLIGENCE_DEPLOYMENT.md
- MARKET_INTELLIGENCE_DEPLOYMENT_COMPLETE.md
- GITHUB_ACTIONS_SETUP.md
- PHASE2_DEPLOYMENT_GUIDE.md
- SPEC8_BACKFILL_DEPLOYMENT_GUIDE.md
- SPEC8_DEPLOYMENT_SUCCESS.md
- RESAMPLING_DEPLOYMENT_GUIDE.md
- FREE_BACKFILL_AUTOMATION_GUIDE.md

### 3. Migration Documentation → `docs/migration/`
- ALPACA_DEPLOYMENT_FIX.md
- ALPACA_FIX_CHECKLIST.txt
- ALPACA_FIX_PLAN.md
- ALPACA_FIX_SUMMARY.md
- ALPACA_INTEGRATION_COMPLETE.md
- ALPACA_INTEGRATION_SUMMARY.md
- ALPACA_MIGRATION_SUMMARY.md
- ALPACA_OPTIMIZATION_SUMMARY.md
- ALPACA_PROVIDER_STRATEGY.md
- ALPACA_REQUIREMENTS_CHECKLIST.md
- MIGRATION_POLYGON_TO_YFINANCE.md
- EXECUTE_ALPACA_FIX.md

### 4. Feature Implementation → `docs/features/`
- AUTOMATED_BACKFILL_SUCCESS.md
- BACKFILL_SETUP.md
- BACKFILL_SETUP_COMPLETE.md
- BATCH_DATA_FLOW.md
- BATCH_FINAL_STATUS.md
- BATCH_REPAIR_COMPLETE.md
- BATCH_REPAIR_GUIDE.md
- BATCH_ROOT_CAUSE_AND_SOLUTION.md
- BATCH_STATUS_CURRENT.md
- BATCH_SYSTEM_BLOCKER.md
- BATCH_SYSTEM_FINAL_SUMMARY.md
- CLIENT_UI_INTEGRATION_COMPLETE.md
- HYDRATION_FIX_SUMMARY.md
- HYDRATION_SYSTEM_STATUS.md
- INTRADAY_BACKFILL_FIX.md
- INTRADAY_BACKFILL_GUIDE.md
- INTRADAY_FIX_SUMMARY.md
- LIVE_SYMBOL_SEARCH_FIX.md
- OPTIONS_RANKER_DETAIL_VIEW.md
- SUPERTREND_AI_IMPLEMENTATION.md
- TRADINGVIEW_ALIGNMENT_COMPLETE.md
- WEBCHART_PHASE1_IMPLEMENTATION.md
- WEBCHART_QUICKSTART.md
- WEBCHART_TESTING_GUIDE.md
- SPEC8_UX_ENHANCEMENTS.md

### 5. Troubleshooting & Fixes → `docs/troubleshooting/`
- CHART_ACCURACY_CHECKLIST.md
- CHART_DATA_TROUBLESHOOTING.md
- CHART_FIXES_SUMMARY.md
- CHART_LOADING_FIXES.md
- CHART_RENDERING_FIX_2026-01-04.md
- CHART_STANDARDS.md
- DATA_ACCURACY_FIX.md
- DATA_COLLECTION_AUDIT.md
- DATA_HEALTH_CHECK.md
- DATA_QUALITY_FIX_2026-01-04.md
- FIXES_SUMMARY.md
- INDICATOR_FIX_2026-01-04.md
- TROUBLESHOOTING_WORKFLOW_ERRORS.md
- MISSING_MODEL_FILES.md
- POLYGON_RATE_LIMIT_OPTIMIZATION.md

### 6. Quick Start Guides → `docs/`
- QUICKSTART_BACKFILL.md
- QUICKSTART_RANKING_JOBS.md
- QUICK_START_CHECKLIST.md
- QUICK_START_DATA_SEPARATION.md
- README_BACKFILL.md
- WATCHLIST_BACKFILL.md
- WATCHLIST_RELOAD_GUIDE.md

### 7. Project Management → `docs/` (keep recent) or `docs/archived/`
- BUILD_SUCCESS_SUMMARY.md
- COMMIT_MESSAGE.md
- FINAL_SUMMARY.md
- IMPLEMENTATION_SUMMARY.md
- PHASE2_BATCH_BACKFILL_GUIDE.md
- PHASE6.5_COMPLETION_SUMMARY.md
- PHASE6_COMPLETION_SUMMARY.md
- COST_COMPARISON_AND_RECOMMENDATION.md
- SUPABASE_USAGE_AUDIT.md
- SUPABASE_ALPACA_DATABASE_UPDATES.md
- SCHEMA_REFRESH_INSTRUCTIONS.md
- CONFIGURE_PGCRON.md

### 8. Xcode Scripts → `scripts/xcode/`
- add_chartdatav2_to_xcode.py
- add_files_to_xcode.py
- add_files_to_xcode_simple.sh
- add_mlreportcard_to_xcode.sh
- add_new_files_to_xcode.sh
- add_timeframe_to_xcode.py
- add_webchart_files.sh
- add_webchart_to_xcode.py
- add_webchartcontrols.py
- ADD_FILES_TO_XCODE.md
- XCODE_PROJECT_UPDATED.md

### 9. Database Scripts → `scripts/database/`
- APPLY_CRITICAL_FIXES.sql
- CLEANUP_DUPLICATES.sql
- DELETE_CORRUPTED_BARS.sql
- FIX_BAD_POLYGON_DATA.sql
- RUN_CLEANUP_NOW.sql
- check-aapl-data.sql
- check-aapl-timeline.sql
- check-constraints.sql
- check-data-health.sql
- deploy_market_intelligence.sql
- diagnose-data-gap.sql
- fix-aapl-data.sql
- full-diagnostic.sql
- setup-backfill-cron.sql

### 10. Validation Scripts → `scripts/validation/`
- check_nvda_prices.py
- compare_tradingview_indicators.py
- debug_nvda_forecast.py
- debug_nvda_swing.py
- diagnose_indicators.py
- test_p0_modules.py
- test_tradingview_alignment.py
- validate_crwd.py
- validate_fixed_indicators.py
- validate_intraday_health.py
- validate_tradingview_data.py
- verify_database_prices.py
- verify_price_accuracy.py

### 11. Analysis Scripts → `scripts/analysis/`
- earnings_analyzer.py
- extrinsic_calculator.py
- pcr_analyzer.py
- pop_calculator.py

### 12. Deployment Scripts → `scripts/deployment/`
- deploy_migrations.py
- execute_migration.py
- purge_and_refetch_data.sh
- purge_and_refetch_us_stocks.sh
- quick-health-check.sh
- quick_verify_db.sh
- test-backfill-worker.sh
- test-backfill.sh
- test-data-health.sh

### 13. TradingView Indicators → `examples/indicators/`
- Enhanced Ranker Integration.txt
- Pivot Levels [BigBeluga.txt
- Support & Resistance Polynomial Regression.txt
- Support and Resistance Logistic Regression.txt
- USAGE EXAMPLE.txt

### 14. Internal Notes → `docs/archived/` or DELETE
- CLAUDE.md
- api_handling.md
- dataintegrity.md
- forecastingprocesses.md
- implemtnation.txt
- improvement_swiftml.txt
- ml_improvement.md
- read_me_starhere.md
- technicals_and_ml_improvement.md
- technicals_ml_improvments.txt
- web-chart-subpanel-wiring.md
- web-chart-tooltip-review.md

### 15. Keep at Root
- README.md
- CHANGELOG.md
- CONTRIBUTING.md
- PROJECT_ORGANIZATION_SUMMARY.md
- PROJECT_REORGANIZATION_PLAN.md
- pyproject.toml
- .gitignore
- .env.example
- requirements.txt (move to ml/ if Python-specific)

---

## 🚀 Execution Plan

### Phase 1: Create Directory Structure
```bash
mkdir -p docs/{architecture,deployment,migration,features,troubleshooting,archived}
mkdir -p scripts/{xcode,database,validation,analysis,deployment}
mkdir -p examples/indicators
```

### Phase 2: Move Files (Automated)
Use a script to move files based on categorization above.

### Phase 3: Update References
- Check for any hardcoded paths in scripts
- Update documentation links
- Verify imports still work

### Phase 4: Clean Up
- Remove duplicate files
- Archive old/obsolete documentation
- Update README with new structure

---

## ⚠️ Safety Measures

1. **Git commit before moving** - Easy rollback if needed
2. **Test after moving** - Verify nothing broke
3. **Keep backups** - Archive folder for old docs
4. **Update gradually** - Move in batches, test each batch

---

## 📝 Post-Reorganization Tasks

- [ ] Update README.md with new structure
- [ ] Add README.md to each docs/ subfolder explaining contents
- [ ] Update .gitignore if needed
- [ ] Create index.md in docs/ linking to all documentation
- [ ] Archive truly obsolete files

---

**Ready to execute?** This will clean up 100+ files from root!
