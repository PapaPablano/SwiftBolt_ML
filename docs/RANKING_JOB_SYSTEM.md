# Options Ranking Job System - Complete Guide

## Overview

The options ranking system uses a **job queue pattern** to handle ranking requests asynchronously. When users click "Generate Rankings" in the app, jobs are queued in the database and processed by a worker script.

## Architecture

```
Swift App (Generate Rankings button)
    ↓
Edge Function: /trigger-ranking-job
    ↓
Database: ranking_jobs table (job queue)
    ↓
Python Worker: ranking_job_worker.py
    ↓
Python Script: options_ranking_job.py
    ↓
Database: options_ranks table (results)
    ↓
Edge Function: /options-rankings
    ↓
Swift App (displays ranked options)
```

## Components

### 1. Database Job Queue (`ranking_jobs` table)

**Schema**:
- `id`: Job UUID
- `symbol`: Stock symbol to rank
- `status`: `pending` → `running` → `completed` | `failed`
- `priority`: Higher numbers processed first (default: 0)
- `retry_count` / `max_retries`: Auto-retry logic
- `error_message`: Error details if failed

**Functions**:
- `get_next_ranking_job()`: Atomically fetch and lock next job
- `complete_ranking_job(job_id)`: Mark job as successful
- `fail_ranking_job(job_id, error_msg)`: Mark job as failed (auto-retries if < max_retries)

### 2. Edge Function: `/trigger-ranking-job`

**Endpoint**: `POST /functions/v1/trigger-ranking-job`

**Request**:
```json
{
  "symbol": "AAPL",
  "priority": 0  // Optional
}
```

**Response**:
```json
{
  "message": "Ranking job queued for AAPL",
  "symbol": "AAPL",
  "jobId": "uuid-here",
  "estimatedCompletionSeconds": 30,
  "queuePosition": 0
}
```

**Features**:
- Deduplication: Won't create duplicate jobs for same symbol within 5 minutes
- Queue position tracking
- Estimated completion time based on queue length

### 3. Python Worker: `ranking_job_worker.py`

**Purpose**: Poll the job queue and execute ranking jobs

**Usage**:

```bash
# Process all pending jobs once
cd ml
source venv/bin/activate
python src/ranking_job_worker.py

# Run continuously (watch mode) - polls every 10 seconds
python src/ranking_job_worker.py --watch

# Custom poll interval (30 seconds)
python src/ranking_job_worker.py --watch --interval 30
```

**How It Works**:
1. Calls `get_next_ranking_job()` to fetch and lock a job
2. Runs `options_ranking_job.py --symbol SYMBOL` as subprocess
3. Marks job as `completed` or `failed` based on result
4. Repeats until queue is empty
5. In watch mode: waits N seconds and checks again

### 4. Ranking Script: `options_ranking_job.py`

Unchanged - same script as before that:
1. Fetches OHLC data for underlying
2. Fetches options chain
3. Calculates ML scores
4. Saves top 100 contracts to `options_ranks` table

## Usage Workflows

### For Development (Manual Worker)

1. **User clicks "Generate Rankings" for AAPL in app**
2. **Job is queued** (you'll see waiting indicator)
3. **In terminal, run worker**:
   ```bash
   cd ml
   source venv/bin/activate
   python src/ranking_job_worker.py
   ```
4. **Worker processes job** (18-30 seconds)
5. **App auto-refreshes and shows rankings** ✅

### For Production (Auto Worker)

#### Option A: Run Worker as Background Service

```bash
# Using systemd (Linux), launchd (macOS), or PM2 (Node.js process manager)
cd ml
source venv/bin/activate
python src/ranking_job_worker.py --watch --interval 10

# Keep this running 24/7 to auto-process jobs
```

#### Option B: Scheduled Task (Cron)

```bash
# Run worker every minute to process any pending jobs
* * * * * cd /path/to/ml && venv/bin/python src/ranking_job_worker.py >> /var/log/ranking_worker.log 2>&1
```

#### Option C: Cloud Function (Future)

Deploy worker as:
- **Google Cloud Run** (container with Python)
- **AWS Lambda** (Python runtime)
- **Trigger**: Cloud Scheduler or database trigger

## Testing

### End-to-End Test

```bash
# 1. Trigger job via API
curl -X POST \
  -H "Authorization: Bearer YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL"}' \
  "https://YOUR_PROJECT.supabase.co/functions/v1/trigger-ranking-job"

# Returns: {"jobId": "...", "queuePosition": 0}

# 2. Run worker
cd ml
source venv/bin/activate
python src/ranking_job_worker.py

# Output: "✅ Successfully processed job ... for AAPL"

# 3. Verify rankings
curl -H "Authorization: Bearer YOUR_SERVICE_KEY" \
  "https://YOUR_PROJECT.supabase.co/functions/v1/options-rankings?symbol=AAPL&limit=5"

# Returns: 5 ranked options with ML scores
```

### Check Job Status Manually

```sql
-- View all pending jobs
SELECT * FROM ranking_jobs WHERE status = 'pending' ORDER BY priority DESC, created_at ASC;

-- View recent completed jobs
SELECT * FROM ranking_jobs WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 10;

-- View failed jobs
SELECT symbol, error_message, retry_count FROM ranking_jobs WHERE status = 'failed';

-- Clear old jobs (7+ days)
SELECT cleanup_old_ranking_jobs();
```

## Troubleshooting

### Job Stuck in "pending"

**Problem**: Job never gets processed

**Solutions**:
1. Check if worker is running: `ps aux | grep ranking_job_worker`
2. Run worker manually to process queue
3. Check database for job: `SELECT * FROM ranking_jobs WHERE symbol = 'AAPL';`

### Job Failed with Error

**Problem**: Job status is `failed`

**Solutions**:
1. Check error message: `SELECT error_message FROM ranking_jobs WHERE symbol = 'AAPL' ORDER BY created_at DESC LIMIT 1;`
2. Common causes:
   - Missing OHLC data → Fetch chart first to auto-populate
   - Missing symbol in database → Add symbol first
   - Python dependencies → Reinstall venv
3. Job will auto-retry up to 3 times

### App Shows "No rankings available"

**Causes**:
1. Job is still pending/running (check queue)
2. Job failed (check error message)
3. OHLC data missing (chart needs to be viewed first)

**Quick Fix**:
```bash
# 1. View chart to populate OHLC
curl "https://YOUR_PROJECT.supabase.co/functions/v1/chart?symbol=AAPL&timeframe=d1"

# 2. Trigger ranking job
curl -X POST ... /trigger-ranking-job -d '{"symbol":"AAPL"}'

# 3. Process job
python src/ranking_job_worker.py
```

## Performance

- **Job Processing Time**: 18-30 seconds per symbol
- **Queue Throughput**: ~2-3 symbols/minute (single worker)
- **Scalability**: Run multiple workers in parallel for higher throughput
- **Database**: Uses `FOR UPDATE SKIP LOCKED` for lock-free job distribution

## Monitoring

### Key Metrics to Track

1. **Queue Depth**: Number of pending jobs
   ```sql
   SELECT COUNT(*) FROM ranking_jobs WHERE status = 'pending';
   ```

2. **Success Rate**: % of jobs that complete successfully
   ```sql
   SELECT
     status,
     COUNT(*) as count,
     ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
   FROM ranking_jobs
   GROUP BY status;
   ```

3. **Average Processing Time**: Time from created to completed
   ```sql
   SELECT
     AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_seconds
   FROM ranking_jobs
   WHERE status = 'completed'
     AND completed_at > NOW() - INTERVAL '24 hours';
   ```

## Future Enhancements

### Batch Processing

Process multiple symbols in one job:
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "priority": 5
}
```

### Webhook Notifications

Notify app when job completes:
```typescript
// In worker, after job completes
await fetch('https://app.com/webhook/ranking-complete', {
  body: JSON.stringify({ jobId, symbol, success: true })
});
```

### Real-time Status Updates

Use Supabase Realtime to subscribe to job status changes in the app:
```swift
supabase.from("ranking_jobs")
  .on(.update, { jobId: myJobId })
  .subscribe { change in
    if change.new.status == "completed" {
      // Refresh rankings UI
    }
  }
```

## Summary

✅ **What Works Now**:
- Queue-based job system with database persistence
- Edge Function to trigger jobs from app
- Python worker to process jobs
- Auto-retry on failures
- Job deduplication
- Queue position tracking

⚠️ **What Requires Manual Action**:
- Running the worker (needs to be started manually or as service)
- Ensuring OHLC data exists before ranking (chart must be viewed first)

🚀 **Production Ready**:
- Deploy worker as background service/container
- Set up monitoring and alerting
- Configure auto-scaling based on queue depth
