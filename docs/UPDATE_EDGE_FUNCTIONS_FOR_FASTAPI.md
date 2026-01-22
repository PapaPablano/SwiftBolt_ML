# Update Edge Functions for FastAPI

This guide shows how to update your Supabase Edge Functions to call the FastAPI server instead of executing Python scripts directly.

## Overview

Instead of using `Deno.Command` to execute Python scripts, Edge Functions will make HTTP requests to your FastAPI server.

## Step 1: Update Environment Variables

In your Supabase project, set the FastAPI server URL:

```bash
# In Supabase Dashboard → Edge Functions → Environment Variables
FASTAPI_URL=https://your-fastapi-server.com
# Or for local testing:
# FASTAPI_URL=http://localhost:8000
```

## Step 2: Update Edge Functions

### Example: technical-indicators

**Before (executing Python script):**
```typescript
const pythonCmd = new Deno.Command("python3", {
  args: [scriptPath, "--symbol", symbol, "--timeframe", timeframe],
  stdout: "piped",
  stderr: "piped",
});
const { code, stdout, stderr } = await pythonCmd.output();
```

**After (calling FastAPI):**
```typescript
const fastapiUrl = Deno.env.get("FASTAPI_URL") || "http://localhost:8000";
const response = await fetch(
  `${fastapiUrl}/api/v1/technical-indicators?symbol=${symbol}&timeframe=${timeframe}`
);
const result = await response.json();
```

## Step 3: Update All 5 Edge Functions

### 1. technical-indicators/index.ts

Replace the `getTechnicalIndicators` function:

```typescript
async function getTechnicalIndicators(
  symbol: string,
  timeframe: string
): Promise<TechnicalIndicatorsResponse> {
  const fastapiUrl = Deno.env.get("FASTAPI_URL");
  if (!fastapiUrl) {
    throw new Error("FASTAPI_URL environment variable not set");
  }

  const url = new URL(`${fastapiUrl}/api/v1/technical-indicators`);
  url.searchParams.set("symbol", symbol);
  url.searchParams.set("timeframe", timeframe);

  const response = await fetch(url.toString(), {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}
```

### 2. backtest-strategy/index.ts

Replace the `runBacktest` function:

```typescript
async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  const fastapiUrl = Deno.env.get("FASTAPI_URL");
  if (!fastapiUrl) {
    throw new Error("FASTAPI_URL environment variable not set");
  }

  const response = await fetch(`${fastapiUrl}/api/v1/backtest-strategy`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      symbol: request.symbol,
      strategy: request.strategy,
      startDate: request.startDate,
      endDate: request.endDate,
      timeframe: request.timeframe,
      initialCapital: request.initialCapital,
      params: request.params,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}
```

### 3. walk-forward-optimize/index.ts

Replace the `runWalkForward` function:

```typescript
async function runWalkForward(
  request: WalkForwardRequest
): Promise<WalkForwardResponse> {
  const fastapiUrl = Deno.env.get("FASTAPI_URL");
  if (!fastapiUrl) {
    throw new Error("FASTAPI_URL environment variable not set");
  }

  const response = await fetch(`${fastapiUrl}/api/v1/walk-forward-optimize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      symbol: request.symbol,
      horizon: request.horizon,
      forecaster: request.forecaster,
      timeframe: request.timeframe,
      trainWindow: request.trainWindow,
      testWindow: request.testWindow,
      stepSize: request.stepSize,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}
```

### 4. portfolio-optimize/index.ts

Replace the `optimizePortfolio` function:

```typescript
async function optimizePortfolio(
  request: PortfolioOptimizeRequest
): Promise<PortfolioOptimizeResponse> {
  const fastapiUrl = Deno.env.get("FASTAPI_URL");
  if (!fastapiUrl) {
    throw new Error("FASTAPI_URL environment variable not set");
  }

  const response = await fetch(`${fastapiUrl}/api/v1/portfolio-optimize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      symbols: request.symbols,
      method: request.method,
      lookbackDays: request.lookbackDays,
      riskFreeRate: request.riskFreeRate,
      targetReturn: request.targetReturn,
      minWeight: request.minWeight,
      maxWeight: request.maxWeight,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}
```

### 5. stress-test/index.ts

Replace the `runStressTest` function:

```typescript
async function runStressTest(
  request: StressTestRequest
): Promise<StressTestResponse> {
  const fastapiUrl = Deno.env.get("FASTAPI_URL");
  if (!fastapiUrl) {
    throw new Error("FASTAPI_URL environment variable not set");
  }

  const response = await fetch(`${fastapiUrl}/api/v1/stress-test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      positions: request.positions,
      prices: request.prices,
      scenario: request.scenario,
      customShocks: request.customShocks,
      varLevel: request.varLevel,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return await response.json();
}
```

## Step 4: Remove Python Script Path Logic

You can now remove:
- `getPythonScriptPath()` functions
- `Deno.Command` imports and usage
- Python script path constants

## Step 5: Add Error Handling

Add timeout and retry logic:

```typescript
async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout = 30000
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === "AbortError") {
      throw new Error("Request timeout");
    }
    throw error;
  }
}
```

## Step 6: Test Locally

1. Start FastAPI server:
```bash
cd ml
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Set environment variable in Supabase CLI:
```bash
supabase secrets set FASTAPI_URL=http://localhost:8000
```

3. Test Edge Function:
```bash
supabase functions serve technical-indicators
```

## Step 7: Deploy

1. Deploy FastAPI server to your chosen platform
2. Update `FASTAPI_URL` in Supabase environment variables
3. Redeploy Edge Functions:
```bash
supabase functions deploy technical-indicators
supabase functions deploy backtest-strategy
supabase functions deploy walk-forward-optimize
supabase functions deploy portfolio-optimize
supabase functions deploy stress-test
```

## Benefits

- ✅ No Python runtime needed in Edge Functions
- ✅ Better error handling and logging
- ✅ Scalable architecture (FastAPI can handle more load)
- ✅ Easier debugging (check FastAPI logs)
- ✅ Can add authentication, rate limiting, caching

## Troubleshooting

### Connection Errors

- Verify `FASTAPI_URL` is set correctly
- Check FastAPI server is running and accessible
- Verify CORS is configured correctly

### Timeout Errors

- Increase timeout for long-running operations
- Consider async processing for very long operations

### Authentication

If you add API key authentication to FastAPI:

```typescript
headers: {
  "Content-Type": "application/json",
  "X-API-Key": Deno.env.get("FASTAPI_API_KEY") || "",
}
```
