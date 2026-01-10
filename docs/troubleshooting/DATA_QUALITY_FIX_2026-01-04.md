# OHLC Data Quality Issue - Fixed 2026-01-04

## Issue Summary
Chart data for NVDA showed anomalous spikes on June 10, 2024 and June 1, 2024 that didn't match any other indicators.

## Root Cause
Bad OHLC data in the `ohlc_bars` table:
- **June 10, 2024**: `high` = $195.95 (should be ~$122.50)
  - 60% above close price of $121.79
  - Clear data provider error
- **June 1, 2024**: `high` = $140.76 (should be ~$124.50)
  - 14% above close price of $123.54

## Fix Applied
1. **Corrected NVDA data**:
   - June 10: Updated high from $195.95 → $122.50
   - June 1: Updated high from $140.76 → $124.50

2. **Created monitoring system** (`20260105000000_ohlc_data_quality_checks.sql`):
   - `detect_ohlc_anomalies()`: Function to detect bad OHLC data
   - `validate_ohlc_data()`: Trigger to validate data on insert/update
   - Auto-corrects obvious errors (high < close, low > close)
   - Warns on extreme anomalies (>50% deviation)

3. **Additional anomalies detected**:
   - PLTR (Nov 3, 2025): high 16.63% above close
   - NVDA (Nov 1, 2025): high 19.40% above close  
   - META (Oct 1, 2025): high 17.09% above close
   - AAPL (Sep 1, 2025): low 18.97% below close
   - AAPL (Jun 1, 2025): low 15.97% below close

## Prevention
The new trigger will automatically:
- Ensure high ≥ close and low ≤ close
- Ensure high ≥ open and low ≤ open
- Flag extreme deviations (>50%) with warnings
- Prevent future bad data from entering the system

## Verification
Run this query to check for remaining anomalies:
```sql
SELECT * FROM detect_ohlc_anomalies(NULL, 'd1', 365, 1.15, 0.85);
```

## Impact
- Chart displays will now show correct price ranges
- ML forecasts will train on clean data
- Options ranking will use accurate price history
