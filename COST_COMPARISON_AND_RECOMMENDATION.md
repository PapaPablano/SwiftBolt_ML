
```md
# Cost Comparison & Recommendation — Automated Backfill

Goal: automate your historical OHLC backfill without manually running scripts and without paying “lofty AWS fees”, while respecting free-tier provider rate limits and caching all bars in Supabase (your current design). [file:1]

This doc compares a few practical ways to run backfills on a schedule and recommends a default.

Key external references:
- GitHub plan includes 2,000 Actions minutes/month on GitHub Free (private repos) and actions are free for public repos on standard runners. [web:33][web:34]
- GitHub Actions minutes and storage/caches have quotas and billing rules. [web:34]
- Supabase supports scheduling Edge Functions via `pg_cron` + `pg_net`. [web:27]

---

## Assumptions (adjustable)

- Backfill runs every 6 hours (4×/day).
- Backfill is incremental by default (fetch missing ranges only). [file:1]
- Typical “incremental” runtime: 2–10 minutes/run (depends on watchlist size, timeframes, and provider delays).
- You are using Linux runners if using GitHub Actions (cheapest, fastest).
- You are staying inside free-tier API quotas by chunking + delays. [file:1]

---

## Option 1 — GitHub Actions (recommended baseline)

### Cost
- GitHub Free includes **2,000 Actions minutes/month** (private repos) and **500MB artifacts**, with 10GB cache included. [web:34]
- Actions are free for public repos on standard runners. [web:34]
- If you exceed minutes on private repos and you *do not* have a payment method: usage can be blocked once quota is used. [web:34]

### Example monthly usage (ballpark)
If the run takes:
- 5 minutes/run × 4 runs/day × 30 days = 600 minutes/month
- 10 minutes/run × 4 runs/day × 30 days = 1,200 minutes/month

Both are under 2,000 minutes/month. [web:34]

### Operational overhead
- Very low: no servers to manage.
- Great logs and history of every run.

### Risk
- If job runtime increases (more symbols/timeframes), minutes could climb.
- Mitigation: split runs (by symbol group or timeframe) or reduce frequency.

### Verdict
Best blend of free + easy + observable for your use case.

---

## Option 2 — Supabase scheduled Edge Functions (pg_cron + pg_net)

Supabase supports scheduling Edge Functions using database cron + HTTP. [web:27]

### Cost
- Potentially $0 in terms of “extra runner” spend (still depends on your Supabase plan and usage).
- No GitHub minutes consumed.

### Operational overhead
- Medium: you’ll implement the backfill trigger as an Edge Function and set up scheduling in Postgres.
- Debugging can be less ergonomic than GitHub Actions.

### Risk
- Long-running backfills may not fit well in Edge Function execution limits.
- Better suited for “enqueue jobs” + “small work chunks” than for large monolithic backfills.

### Verdict
Strong “all-in Supabase” approach, but typically not the quickest path for Python-heavy workflows.

---

## Option 3 — Free HTTP cron service (cron-job.org)

cron-job.org can call a URL on a schedule for free. [web:9]

### Cost
- Typically $0 for basic use.
- No GitHub minutes.

### Operational overhead
- Low, but you must expose a protected endpoint and manage security.
- You become dependent on a third party cron service.

### Risk
- External dependency.
- If the HTTP call times out, you need a queue approach.

### Verdict
Fine option when GitHub Actions is not available, but less self-contained.

---

## Option 4 — AWS (Lambda / ECS / EC2)

### Cost
- Often “small” at first, but frequently ends up non-zero due to:
  - CloudWatch logs
  - NAT gateways (if misconfigured)
  - Always-on instances
  - Request volume / time
- Also a time cost: ops overhead.

### Operational overhead
- Higher than all alternatives.

### Verdict
Avoid for this use case unless there are other AWS reasons.

---

## Decision matrix

| Option | Direct cost | Setup time | Ops burden | Best for |
|---|---:|---:|---:|---|
| GitHub Actions | $0 (within quota) [web:34] | ~15–30 min | Low | Most cases |
| Supabase scheduling | $0 (often) [web:27] | ~30–90 min | Medium | “Keep it in Supabase” |
| cron-job.org | $0 [web:9] | ~15–30 min | Medium (security) | Simple HTTP triggers |
| AWS | $ | 1–3 hrs | Higher | Enterprises / existing AWS infra |

---

## Recommendation

### Default recommendation: GitHub Actions every 6 hours
Because:
- You can keep the backfill logic in Python (no rewrite).
- It’s fast to iterate (push code, run workflow, check logs).
- You get strong observability.
- You are likely within the free minute quota for incremental backfills. [web:34]

This directly implements your “scheduled backfill job” concept from your backfill system doc, just at a 6-hour cadence. [file:1]

---

## Keeping it free long-term

To stay within free tiers and avoid surprise blocks/cost:

1) Make incremental the default
- Only fetch missing windows. [file:1]

2) Bound work per run
- Limit symbols processed per run (e.g., “top 30 watchlist”).
- Or process in batches (A–M then N–Z).

3) Reduce expensive timeframes
- Intraday backfill is the most costly.
- Run intraday less frequently (e.g., daily) and daily/weekly more frequently.

4) Use DB dedupe + cache aggressively
- Unique constraints prevent double inserts.
- Avoid refetching already-covered ranges. [file:1]

5) Monitor “minutes per month”
- Watch Actions runtime; if you approach 2,000 minutes/month, split workloads or reduce cadence. [web:34]

---

## Next file

Reply “next” to get File 6/6: `IMPLEMENTATION_SUMMARY.md`.
```
