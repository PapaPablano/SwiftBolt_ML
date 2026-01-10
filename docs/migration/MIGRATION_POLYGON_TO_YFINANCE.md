# Migration Plan: Polygon → Yahoo Finance for Historical Data

## Why Switch?

**Polygon Issues Found:**
- 8 corrupted bars for AAPL with extreme intraday ranges (20-44%)
- Bad data on first-of-month dates and non-trading days
- Requires constant data quality monitoring and cleanup

**Yahoo Finance Benefits:**
- Free and reliable
- No data quality issues (validated against TradingView)
- Better handling of holidays/weekends
- Built-in data validation

## Migration Steps

### Phase 1: Clean Up Bad Polygon Data (Do Now)

1. **Delete corrupted AAPL bars:**
   ```bash
   # Run in Supabase SQL Editor
   psql < FIX_BAD_POLYGON_DATA.sql
   ```

2. **Check other symbols for bad data:**
   ```bash
   cd ml
   python3 -m src.scripts.validate_all_symbols
   ```

3. **Delete all bars with extreme ranges (>20%):**
   ```sql
   DELETE FROM ohlc_bars_v2
   WHERE is_forecast = false
     AND timeframe = 'd1'
     AND ((high - low) / close * 100) > 20;
   ```

### Phase 2: Backfill with Yahoo Finance (Next)

1. **Install yfinance:**
   ```bash
   cd ml
   pip install yfinance
   pip freeze > requirements.txt
   ```

2. **Backfill all symbols:**
   ```bash
   # Single symbol test
   python3 -m src.scripts.backfill_ohlc_yfinance --symbol AAPL --days 730

   # All watchlist symbols
   python3 -m src.scripts.backfill_ohlc_yfinance --days 730
   ```

3. **Verify data quality:**
   ```bash
   # Check for any remaining bad data
   python3 -m src.scripts.validate_all_symbols
   ```

### Phase 3: Update Data Sources (Final)

1. **Update Edge Function to prefer yfinance:**
   - Modify `get_chart_data_v2` to prioritize `provider='yfinance'`
   - Keep Polygon as fallback for symbols not in yfinance

2. **Update scheduled jobs:**
   - Replace `deep_backfill_ohlc_v2.py` with `backfill_ohlc_yfinance.py`
   - Keep Tradier for intraday data (works well)

3. **Add data validation:**
   - Reject bars with extreme intraday ranges (>20%)
   - Reject bars on weekends/holidays
   - Reject zero-range bars

## Data Provider Strategy

| Data Type | Provider | Reason |
|-----------|----------|--------|
| **Historical (d1)** | Yahoo Finance | Reliable, free, clean data |
| **Intraday (real-time)** | Tradier | Works well, no issues found |
| **Forecast** | ML Models | Internal generation |

## Validation Checks

After migration, verify:
- [ ] No bars with >20% intraday range
- [ ] No bars on weekends (Sat/Sun)
- [ ] No zero-range bars (H=L=O=C)
- [ ] All dates match Yahoo Finance
- [ ] Charts render smoothly without discontinuities

## Rollback Plan

If issues arise:
1. Keep both `provider='polygon'` and `provider='yfinance'` data
2. Edge Function can switch between providers via query param
3. Can delete yfinance data and revert to Polygon if needed

## Timeline

- **Today**: Clean up bad Polygon data, test yfinance backfill
- **Tomorrow**: Backfill all symbols with yfinance
- **This Week**: Update Edge Function, deprecate Polygon

## Cost Comparison

| Provider | Cost | Rate Limits | Data Quality |
|----------|------|-------------|--------------|
| Polygon | $200/mo | 5 req/sec | Issues found |
| Yahoo Finance | Free | Reasonable | Excellent |
| Tradier | Included | Good | Good |

**Savings: $200/month** by switching to Yahoo Finance for historical data.
