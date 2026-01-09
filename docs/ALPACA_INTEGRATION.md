# Alpaca Market Data API Integration

## Overview

SwiftBoltML now integrates with [Alpaca Market Data API](https://alpaca.markets) as a primary data provider for historical and real-time market data. Alpaca provides high-quality, reliable market data with excellent coverage and competitive pricing.

## Features

- **Historical Data**: 7+ years of historical OHLC bars for US stocks
- **Real-time Data**: Live quotes and bars via REST API
- **WebSocket Streaming**: Event-based real-time data (future enhancement)
- **News Feed**: Multi-source news aggregation
- **High Rate Limits**: 200 calls/min on free tier, unlimited on paid tiers
- **Multiple Timeframes**: 1Min, 5Min, 15Min, 30Min, 1Hour, 4Hour, 1Day, 1Week, 1Month

## Getting Started

### 1. Create an Alpaca Account

1. Visit [Alpaca Dashboard](https://app.alpaca.markets/brokerage/dashboard/overview)
2. Sign up for a free account (no credit card required)
3. Navigate to the API Keys section
4. Generate new API keys (Key ID and Secret Key)

### 2. Configure Environment Variables

Add your Alpaca credentials to your environment:

```bash
# In your .env file or Supabase Edge Function secrets
ALPACA_API_KEY=your-alpaca-api-key-id
ALPACA_API_SECRET=your-alpaca-api-secret-key
```

For Supabase Edge Functions, set these as secrets:

```bash
# Using Supabase CLI
supabase secrets set ALPACA_API_KEY=your-key
supabase secrets set ALPACA_API_SECRET=your-secret
```

### 3. Deploy the Migration

Apply the database migration to enable Alpaca support:

```bash
cd backend/supabase
supabase db push
```

Or manually apply the migration:

```bash
psql $DATABASE_URL -f migrations/20260109150000_add_alpaca_provider.sql
```

## Architecture

### Provider Hierarchy

Alpaca is configured as the **primary provider** when available, with automatic fallback:

1. **Alpaca** (primary) - Best data quality and coverage
2. **Yahoo Finance** (fallback) - Free historical data
3. **Polygon** (fallback) - Via Massive API
4. **Tradier** (intraday) - Real-time intraday data

### Data Flow

```
Client Request
    ↓
Edge Function (chart-data-v2)
    ↓
Provider Router
    ↓
Alpaca Client → Alpaca API
    ↓ (if fails)
Fallback to Yahoo/Polygon
    ↓
Database (ohlc_bars_v2)
    ↓
Client Response
```

### Provider Selection Logic

The `get_chart_data_v2` database function automatically selects the best provider:

- **Historical data** (dates < today): Prefers Alpaca → Yahoo Finance → Polygon
- **Intraday data** (today): Prefers Alpaca → Tradier
- **Forecasts** (dates > today): ML-generated forecasts only

## API Reference

### AlpacaClient Methods

#### `getQuote(symbols: string[]): Promise<Quote[]>`

Fetch real-time quotes for one or more symbols.

```typescript
const quotes = await alpacaClient.getQuote(['AAPL', 'MSFT']);
// Returns: [{ symbol, price, timestamp, volume, change, ... }]
```

#### `getHistoricalBars(request: HistoricalBarsRequest): Promise<Bar[]>`

Fetch historical OHLC bars.

```typescript
const bars = await alpacaClient.getHistoricalBars({
  symbol: 'AAPL',
  timeframe: 'd1', // m1, m5, m15, m30, h1, h4, d1, w1, mn1
  start: startTimestamp,
  end: endTimestamp
});
// Returns: [{ timestamp, open, high, low, close, volume }]
```

#### `getNews(request: { symbol: string; limit?: number }): Promise<NewsItem[]>`

Fetch news for a symbol.

```typescript
const news = await alpacaClient.getNews({ symbol: 'AAPL', limit: 50 });
// Returns: [{ id, headline, summary, source, url, publishedAt, sentiment }]
```

## Rate Limits

### Free Tier
- **REST API**: ~200 calls/minute
- **WebSocket**: Real-time, limited to ~30 symbols
- **Data Delay**: 15-minute delay for REST, real-time for WebSocket

### Paid Tier (Algo Trader Plus)
- **REST API**: Unlimited calls
- **WebSocket**: Real-time, unlimited symbols
- **Data Delay**: Real-time for both REST and WebSocket
- **Exchange Coverage**: All US exchanges (vs IEX-only on free tier)

### Configuration

Adjust rate limits via environment variables:

```bash
ALPACA_MAX_RPS=10      # Max requests per second
ALPACA_MAX_RPM=200     # Max requests per minute
```

## Data Quality

### Advantages
- ✅ **7+ years** of historical data
- ✅ **Split-adjusted** pricing
- ✅ **High accuracy** - institutional-grade data
- ✅ **Consistent timestamps** - all in UTC
- ✅ **Trade-level data** available (tick data)
- ✅ **Volume-weighted average price** (VWAP) included

### Comparison with Other Providers

| Feature | Alpaca | Yahoo Finance | Polygon | Tradier |
|---------|--------|---------------|---------|---------|
| Historical Coverage | 7+ years | 20+ years | 2+ years | Limited |
| Real-time Data | ✅ | ❌ (15-min delay) | ✅ | ✅ |
| Rate Limits | 200/min free | Unofficial | 5/min free | 120/min |
| Data Quality | Excellent | Good | Excellent | Good |
| Cost | Free tier available | Free | Paid | Free tier |
| Options Data | ✅ (OPRA) | ✅ | ✅ | ✅ |

## Usage Examples

### Backfilling Historical Data

```typescript
// In your backfill script
import { getProviderRouter } from './_shared/providers/factory.ts';

const router = getProviderRouter();
const bars = await router.getHistoricalBars({
  symbol: 'AAPL',
  timeframe: 'd1',
  start: Math.floor(Date.now() / 1000) - (365 * 24 * 60 * 60), // 1 year ago
  end: Math.floor(Date.now() / 1000)
});

// Store in database
for (const bar of bars) {
  await supabase.from('ohlc_bars_v2').insert({
    symbol_id: symbolId,
    timeframe: 'd1',
    ts: new Date(bar.timestamp * 1000),
    open: bar.open,
    high: bar.high,
    low: bar.low,
    close: bar.close,
    volume: bar.volume,
    provider: 'alpaca',
    is_forecast: false,
    is_intraday: false,
    data_status: 'complete'
  });
}
```

### Real-time Quote Updates

```typescript
// In your quote refresh function
const router = getProviderRouter();
const quotes = await router.getQuote(['AAPL', 'MSFT', 'GOOGL']);

for (const quote of quotes) {
  console.log(`${quote.symbol}: $${quote.price} (${quote.changePercent}%)`);
}
```

## Troubleshooting

### Authentication Errors

**Error**: `401 Unauthorized`

**Solution**: Verify your API credentials:
```bash
# Check if secrets are set
supabase secrets list

# Re-set if needed
supabase secrets set ALPACA_API_KEY=your-key
supabase secrets set ALPACA_API_SECRET=your-secret
```

### Rate Limit Errors

**Error**: `429 Too Many Requests`

**Solution**: The provider router automatically handles rate limiting with exponential backoff. If you're consistently hitting limits:

1. Reduce polling frequency
2. Use WebSocket streaming instead of REST polling
3. Upgrade to a paid tier for higher limits
4. Implement client-side caching

### No Data Returned

**Error**: Empty bars array

**Possible causes**:
1. Symbol not found - verify ticker symbol
2. Date range outside available data - check start/end dates
3. Market closed - no intraday data outside market hours
4. Invalid timeframe - use supported timeframes only

## Future Enhancements

### WebSocket Streaming (Planned)

Real-time streaming via WebSocket for live data:

```typescript
// Future implementation
const stream = alpacaClient.createStream(['AAPL', 'MSFT']);

stream.on('trade', (trade) => {
  console.log(`${trade.symbol}: ${trade.price}`);
});

stream.on('quote', (quote) => {
  console.log(`${quote.symbol}: bid=${quote.bid} ask=${quote.ask}`);
});

stream.connect();
```

### Options Chain Support

Alpaca provides OPRA options data:

```typescript
// Future implementation
const chain = await alpacaClient.getOptionsChain({
  underlying: 'AAPL',
  expiration: '2026-01-17'
});
```

## Resources

- [Alpaca Documentation](https://docs.alpaca.markets)
- [Market Data API Guide](https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data)
- [API Reference](https://docs.alpaca.markets/reference)
- [Rate Limits](https://docs.alpaca.markets/docs/about-market-data-api#rate-limits)
- [Data Plans](https://alpaca.markets/data)

## Support

For issues related to:
- **Alpaca API**: Contact [Alpaca Support](https://alpaca.markets/support)
- **SwiftBoltML Integration**: Open an issue on GitHub or contact the development team

## License

This integration follows the same license as SwiftBoltML. Alpaca Market Data API usage is subject to [Alpaca's Terms of Service](https://alpaca.markets/legal).
