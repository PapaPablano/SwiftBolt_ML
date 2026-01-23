# Quick Reference - Entry/Exit Ranking System
## January 23, 2026

## 🚀 Quick Start (Copy & Paste)

### 1. Apply Database Migration

**Via Supabase Dashboard** (Recommended):
```
1. Go to: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql
2. Click: "New Query"
3. Copy/paste: supabase/migrations/20260123_add_entry_exit_rankings.sql
4. Click: "Run"
5. Look for: "Migration successful: All 8 columns added"
```

### 2. Run Python Jobs

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

# ENTRY mode - Find buying opportunities
python -m src.options_ranking_job --symbol AAPL --mode entry

# EXIT mode - Detect selling signals
python -m src.options_ranking_job --symbol AAPL --mode exit --entry-price 2.50

# MONITOR mode - Balanced ranking (default)
python -m src.options_ranking_job --symbol AAPL --mode monitor
```

### 3. Verify Data

```sql
-- Count records by mode
SELECT ranking_mode, COUNT(*) 
FROM options_ranks 
WHERE underlying_symbol_id = (SELECT id FROM symbols WHERE ticker = 'AAPL')
GROUP BY ranking_mode;

-- View top entry opportunities
SELECT contract_symbol, entry_rank, entry_value_score, catalyst_score
FROM options_ranks
WHERE ranking_mode = 'entry'
ORDER BY entry_rank DESC
LIMIT 5;

-- View top exit signals
SELECT contract_symbol, exit_rank, profit_protection_score, time_urgency_score
FROM options_ranks
WHERE ranking_mode = 'exit'
ORDER BY exit_rank DESC
LIMIT 5;
```

### 4. Test API

Replace `YOUR_ANON_KEY` with your actual Supabase anon key from `.env`:

```bash
# Get your key from .env
grep SUPABASE_ANON_KEY /Users/ericpeterson/SwiftBolt_ML/.env

# Test ENTRY mode
curl "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL&mode=entry&limit=5" \
  -H "Authorization: Bearer YOUR_ANON_KEY"

# Test EXIT mode
curl "https://cygflaemtmwiwaviclks.supabase.co/functions/v1/options-rankings?symbol=AAPL&mode=exit&limit=5" \
  -H "Authorization: Bearer YOUR_ANON_KEY"
```

---

## 📚 Key Files

### Documentation
- `COMPLETE_MIGRATION_AND_TESTING_GUIDE.md` - Full walkthrough (read this first!)
- `MIGRATION_WALKTHROUGH.md` - Detailed migration steps
- `PYTHON_JOB_UPDATED.md` - Python job usage
- `DATABASE_MIGRATION_GUIDE.md` - Database schema details
- `ENTRY_EXIT_TEST_RESULTS.md` - Test validation results

### Migration Files
- `supabase/migrations/20260123_add_entry_exit_rankings.sql` - Apply migration
- `supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql` - Rollback (if needed)
- `scripts/verify_ranking_migration.sql` - Verification queries

### Code Files (Already Updated ✅)
- `ml/src/options_ranking_job.py` - Python ranking job
- `ml/src/models/options_momentum_ranker.py` - Ranking algorithms
- `backend/supabase/functions/options-rankings/index.ts` - API endpoint
- `client-macos/SwiftBoltML/Models/OptionsRankingResponse.swift` - Swift models

---

## 🎯 Common Commands

### Run Rankings for Different Symbols

```bash
cd /Users/ericpeterson/SwiftBolt_ML/ml

# Single symbol - ENTRY
python -m src.options_ranking_job --symbol MSFT --mode entry

# Single symbol - EXIT (with entry price)
python -m src.options_ranking_job --symbol TSLA --mode exit --entry-price 3.25

# All watchlist symbols (from settings.py)
python -m src.options_ranking_job --mode entry
```

### Query Database

```sql
-- Compare modes for same contract
SELECT 
    contract_symbol,
    ranking_mode,
    CASE ranking_mode
        WHEN 'entry' THEN entry_rank
        WHEN 'exit' THEN exit_rank
        ELSE composite_rank
    END as rank
FROM options_ranks
WHERE contract_symbol LIKE 'AAPL%C00180000%'
ORDER BY ranking_mode;

-- Find best entry opportunities across all symbols
SELECT 
    s.ticker,
    r.contract_symbol,
    r.strike,
    r.entry_rank,
    r.entry_value_score,
    r.catalyst_score
FROM options_ranks r
JOIN symbols s ON r.underlying_symbol_id = s.id
WHERE r.ranking_mode = 'entry'
AND r.entry_rank > 70
ORDER BY r.entry_rank DESC
LIMIT 20;

-- Find positions to exit
SELECT 
    s.ticker,
    r.contract_symbol,
    r.exit_rank,
    r.profit_protection_score,
    r.time_urgency_score
FROM options_ranks r
JOIN symbols s ON r.underlying_symbol_id = s.id
WHERE r.ranking_mode = 'exit'
AND r.exit_rank > 70
ORDER BY r.exit_rank DESC;
```

### Rollback (If Needed)

**Only if something goes wrong:**

```bash
# Via Supabase Dashboard
# Copy/paste: supabase/migrations/20260123_add_entry_exit_rankings_rollback.sql
# Click "Run"
```

---

## 🐛 Troubleshooting

### Migration Issues

```sql
-- Check if migration was applied
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'options_ranks' 
AND column_name IN ('entry_rank', 'exit_rank');
-- Should return 2 rows

-- Check indexes
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'options_ranks' 
AND indexname LIKE '%entry%';
-- Should return 2 indexes
```

### Python Job Issues

```bash
# Check Python environment
python --version  # Should be 3.9+

# Check dependencies
pip list | grep pandas
pip list | grep requests

# Run with verbose output
python -m src.options_ranking_job --symbol AAPL --mode entry 2>&1 | tee debug.log

# Check for errors
grep -i error debug.log
```

### Database Issues

```sql
-- Check for NaN/Inf values
SELECT COUNT(*) 
FROM options_ranks 
WHERE entry_rank::text IN ('NaN', 'Infinity', '-Infinity');
-- Should return 0

-- Check rank ranges
SELECT 
    ranking_mode,
    MIN(CASE ranking_mode WHEN 'entry' THEN entry_rank WHEN 'exit' THEN exit_rank ELSE composite_rank END) as min_rank,
    MAX(CASE ranking_mode WHEN 'entry' THEN entry_rank WHEN 'exit' THEN exit_rank ELSE composite_rank END) as max_rank
FROM options_ranks
GROUP BY ranking_mode;
-- All ranks should be 0-100
```

---

## 📊 Understanding the Modes

### ENTRY Mode (Find Buys)
**Formula**: Value 40% + Catalyst 35% + Greeks 25%  
**Looks for**: Low IV, volume surge, favorable Greeks  
**Best for**: Finding undervalued options with momentum

### EXIT Mode (Detect Sells)
**Formula**: Profit 50% + Deterioration 30% + Time 20%  
**Looks for**: High P&L, momentum decay, time urgency  
**Best for**: Protecting profits, avoiding decay

### MONITOR Mode (Balanced)
**Formula**: Momentum 40% + Value 35% + Greeks 25%  
**Looks for**: Overall strong signals  
**Best for**: General watchlist monitoring

---

## 🎓 Interpreting Results

### Entry Rank Score

| Score | Interpretation | Action |
|-------|----------------|--------|
| 80-100 | Excellent entry opportunity | Consider buying |
| 60-79 | Good entry opportunity | Evaluate carefully |
| 40-59 | Fair opportunity | Wait for better setup |
| 0-39 | Poor entry opportunity | Avoid |

### Exit Rank Score

| Score | Interpretation | Action |
|-------|----------------|--------|
| 80-100 | Strong exit signal | Consider selling |
| 60-79 | Moderate exit signal | Prepare to exit |
| 40-59 | Neutral | Monitor closely |
| 0-39 | Stay in position | Keep holding |

### Combined Strategy

**Buy Signal**: Entry rank > 70, Exit rank < 40  
**Sell Signal**: Exit rank > 70, Entry rank < 40  
**Hold**: Both moderate (40-60)  
**Avoid**: Both low (< 40)

---

## ✅ Checklist

### After Migration
- [ ] Database migration applied (8 columns added)
- [ ] Verification queries return expected results
- [ ] No errors in Supabase logs

### After Python Job
- [ ] ENTRY mode job completes successfully
- [ ] EXIT mode job completes successfully
- [ ] MONITOR mode job completes successfully
- [ ] Database records populated for all modes

### Before Frontend Deploy
- [ ] API returns data for all modes
- [ ] Response times < 500ms
- [ ] No 500 errors in Supabase function logs
- [ ] Frontend models match API response

---

## 🔗 Useful Links

- **Supabase Dashboard**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks
- **SQL Editor**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/sql
- **Function Logs**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/functions
- **Database**: https://supabase.com/dashboard/project/cygflaemtmwiwaviclks/editor

---

## 📞 Need Help?

1. **Check logs**: Supabase Dashboard → Functions → options-rankings → Logs
2. **Review docs**: `COMPLETE_MIGRATION_AND_TESTING_GUIDE.md`
3. **Verify migration**: Run verification queries above
4. **Test with sample**: Use AAPL for quick testing

---

## 🎉 You're All Set!

**Migration**: ✅ Ready to apply  
**Python Job**: ✅ Ready to run  
**API**: ✅ Ready to test  
**Frontend**: ⏸️ Next step

Use this quick reference anytime you need to run rankings or check the system status!
