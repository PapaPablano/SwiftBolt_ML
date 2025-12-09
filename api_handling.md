
***

# Data Provider & Rate-Limiting Design

> High‑level design for integrating Finnhub and Massive under free‑tier constraints in the Stock ML App.

***

## Goals

- Provide a unified abstraction over multiple market‑data providers (Finnhub, Massive).  
- Enforce provider‑specific free‑tier limits (requests per second/minute, data scope).  
- Support caching, graceful degradation, and easy migration to paid tiers or new providers.

***

## Providers Overview

### Finnhub

- **Usage intent:** Personal / non‑commercial free tier; commercial use requires paid plan.  
- **Key limits (free):**  
  - Soft target: ~60 requests per minute per API key.  
  - Hard global cap: 30 requests per second across the account; 429 on violation.  
- **Primary capabilities used in this app:**  
  - Real‑time or near real‑time quotes.  
  - Basic fundamentals and reference data.  
  - Limited historical OHLCV (exact endpoints to be enumerated per use case).

### Massive (Stocks Basic)

- **Usage intent:** Testing and light personal use, not heavy production.  
- **Key limits (free):**  
  - 5 REST API requests per minute for stocks endpoints.  
- **Primary capabilities used in this app:**  
  - US equities coverage.  
  - Up to ~2 years of historical aggregates (minute + daily) and reference data.  
  - Selected technical indicators where needed.

***

## High‑Level Architecture

### Core Components

- `DataProviderAbstraction`  
  - Interface / base class defining operations the app cares about, e.g.:  
    - `getQuote(symbols: string[]): QuoteResult[]`  
    - `getHistoricalBars(symbol: string, timeframe: Timeframe, start, end): Bar[]`  
    - `getFundamentals(symbol: string): Fundamentals`  
  - No provider‑specific types leak out of this layer.

- `FinnhubClient` (implements `DataProviderAbstraction`)  
  - Wraps Finnhub REST endpoints.  
  - Handles Finnhub auth, query construction, pagination, and error mapping.  
  - Uses shared `RateLimiter` and `Cache` components.

- `MassiveClient` (implements `DataProviderAbstraction`)  
  - Wraps Massive REST endpoints for stocks.  
  - Enforces stricter 5‑req/min limit.  
  - Uses shared `RateLimiter` and `Cache` components.

- `ProviderRouter`  
  - Knows which provider to use for each operation and when to fall back.  
  - Example policy:  
    - Real‑time quotes: Finnhub primary; Massive fallback when Finnhub unavailable.  
    - Deep historical (≤2y US minute data): Massive primary (careful with rate); Finnhub fallback if available.  
  - Takes into account provider health, current rate‑limit status, and request priority.

***

## Rate Limiting Design

### Requirements

- Enforce **per‑provider** limits:  
  - Finnhub:  
    - Per‑second bucket: 30 req/s (hard ceiling).  
    - Per‑minute bucket: ~60 req/min (configurable so it can change with plan).  
  - Massive:  
    - Per‑minute bucket: 5 req/min (configurable per plan).  
- Ensure **pre‑emptive throttling**: avoid hitting 429 where possible.  
- Provide a way to **query current usage** for observability.

### Rate Limiter Abstractions

- `RateLimiter` interface  
  - `acquire(provider: ProviderId, cost?: number): Promise<void>`  
  - Throws or rejects when request must be delayed beyond a configured max wait.  

- Implementations (config‑driven):  
  - `TokenBucketRateLimiter` with configurable:  
    - `maxTokensPerSecond`  
    - `maxTokensPerMinute`  
    - `burstMultiplier` (for short spikes)  

- Provider‑specific config (e.g. `rateLimits.json`):  
```json
{
  "finnhub": {
    "maxPerSecond": 30,
    "maxPerMinute": 60
  },
  "massive": {
    "maxPerSecond": 1,
    "maxPerMinute": 5
  }
}
```

- 429 handling:  
  - If external API still returns 429:  
    - Record event in metrics/logs.  
    - Backoff with exponential delay + jitter.  
    - Optionally mark provider as “degraded” in `ProviderRouter` for a short period.

***

## Caching Strategy

### Goals

- Minimize external calls under free tiers.  
- Provide fast responses for common queries.  
- Keep data “fresh enough” for the app’s UX and ML needs.

### Design

- `Cache` interface with `get`, `set`, `invalidate`, and optional `tags`.  
- Primary cache types:  
  - In‑memory LRU for hot, very short‑lived data (e.g., quotes for popular symbols).  
  - Redis or similar for shared cache across instances (optional, depending on infra).

- Suggested TTLs (configurable):  
  - Quotes: 1–5 seconds (interactive UI) or 15–60 seconds (analytics screens).  
  - Fundamentals/reference: hours or days.  
  - Historical bars: effectively immutable; cache and/or persist long term.

- Cache keys should be **provider‑agnostic** at the abstraction layer:  
  - Example key patterns:  
    - `quote:{symbol}`  
    - `bars:{symbol}:{timeframe}:{start}:{end}`  

***

## Error Handling & Degradation

### Error Types

- Provider‑specific errors mapped into unified domain errors:  
  - `RateLimitExceededError`  
  - `ProviderUnavailableError`  
  - `InvalidSymbolError`  
  - `PermissionDeniedError` (e.g., data not available on free plan)

### Degradation Strategy

- On `RateLimitExceededError` for primary provider:  
  - Attempt fallback provider if within its quota and data type is available.  
  - Otherwise return cached data (even if stale beyond normal TTL) with a “stale” flag.  
- On persistent provider failure:  
  - Mark provider as unhealthy in `ProviderRouter` with a cooldown window.  
  - Route new requests to alternate provider when possible.

***

## Configuration & Secrets

- All provider‑specific values must be externalized:  
  - API keys: environment variables or secrets manager.  
  - Base URLs: config with per‑env overrides.  
  - Rate limit numbers: config file or env, so upgrading to paid tiers only requires config changes.

- Example `.env` keys (do not commit values):  
  - `FINNHUB_API_KEY`  
  - `FINNHUB_BASE_URL`  
  - `MASSIVE_API_KEY`  
  - `MASSIVE_BASE_URL`  
  - `FINNHUB_MAX_RPS`, `FINNHUB_MAX_RPM`, `MASSIVE_MAX_RPM`

***

## Testing Plan

- **Unit tests**  
  - Mock HTTP layer and verify each client builds correct URLs, headers, and parses responses.  
  - Test rate‑limiter behavior for burst, sustained load, and backoff.  
  - Verify `ProviderRouter` selection and fallback rules.

- **Integration tests (with sandbox keys)**  
  - Smoke tests that hit each provider at low rate.  
  - Tests that intentionally exceed configured local limit and assert:  
    - No more than N requests leave the process.  
    - Correct errors or fallbacks are triggered.

- **Load simulations**  
  - Synthetic load generator that approximates expected user traffic.  
  - Confirm that effective external QPS/QPM stays within free‑tier ceilings.

***

## Implementation Checklist

- [ ] Define `DataProviderAbstraction` interface.  
- [ ] Implement `FinnhubClient` with config‑driven rate‑limits.  
- [ ] Implement `MassiveClient` with strict 5‑req/min cap.  
- [ ] Implement shared `TokenBucketRateLimiter`.  
- [ ] Implement caching layer with pluggable backends.  
- [ ] Implement `ProviderRouter` with policy configuration.  
- [ ] Add observability (metrics, logs, dashboards) for per‑provider usage and errors.  
- [ ] Write unit and integration tests for all the above.  

