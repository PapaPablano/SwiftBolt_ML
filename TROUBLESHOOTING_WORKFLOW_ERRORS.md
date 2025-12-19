# GitHub Actions Workflow Troubleshooting

Quick fixes for common workflow errors.

---

## ❌ Error: "Field required [type=missing] database_url"

**Full error:**
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
database_url
  Field required [type=missing, input_value={...}, input_type=dict]
```

**Cause:** The `Settings` class was expecting a required `database_url` field that wasn't provided in GitHub Secrets.

**Fix Applied:** ✅ Made `database_url` optional in `ml/config/settings.py` since the backfill script only uses the Supabase REST API, not direct Postgres access.

**Alternative Fix:** Add `DATABASE_URL` to GitHub Secrets if you need it for other ML jobs.

---

## ❌ Error: "No module named 'config.settings'"

**Cause:** Missing dependencies or Python path issue.

**Fix:**
1. Verify `ml/requirements.txt` exists and contains `pydantic-settings`
2. Check workflow installs from correct path:
   ```yaml
   pip install -r ml/requirements.txt
   ```

---

## ❌ Error: "401 Unauthorized"

**Cause:** Invalid Supabase credentials.

**Fix:**
1. Verify `SUPABASE_SERVICE_ROLE_KEY` is the **service role** key (not anon key)
2. Check `SUPABASE_URL` matches your project: `https://YOUR_PROJECT.supabase.co`
3. Secrets are case-sensitive - match exactly

---

## ❌ Error: "Symbol not found in database"

**Cause:** Symbol doesn't exist in `symbols` table.

**Fix:** Add symbol to database:
```sql
INSERT INTO symbols (ticker, name, asset_type)
VALUES ('AAPL', 'Apple Inc.', 'stock')
ON CONFLICT (ticker) DO NOTHING;
```

---

## ❌ Error: "429 Too Many Requests"

**Cause:** API rate limiting.

**Fix:**
1. Increase `RATE_LIMIT_DELAY` in `ml/src/scripts/backfill_ohlc.py`:
   ```python
   RATE_LIMIT_DELAY = 5.0  # Increase from 2.0
   ```
2. Reduce watchlist size
3. Run less frequently (every 12 hours instead of 6)

---

## ✅ Current Status

**Issue:** `database_url` field required error
**Status:** ✅ FIXED - Made field optional
**Next:** Re-run workflow to verify fix

---

## 🔄 How to Re-run Failed Workflow

1. Go to: GitHub → Actions tab
2. Click on the failed workflow run
3. Click: "Re-run all jobs" button (top right)
4. Or trigger a new manual run:
   - Actions → "Automated OHLC Backfill"
   - Run workflow → Symbol: AAPL → Run

---

## 📞 If Issues Persist

**Check these in order:**
1. GitHub Actions logs (most detailed)
2. This troubleshooting guide
3. `docs/BACKFILL_OPERATIONS.md` (full runbook)
4. `BACKFILL_SETUP_COMPLETE.md` (setup checklist)
