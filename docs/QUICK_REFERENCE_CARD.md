# SwiftBolt ML Frameworks Quick Reference Card

Single-page cheat sheet for all four framework layers. Print or bookmark.

---

## 1. REACT HOOK FORM

### Basic Pattern
```typescript
const methods = useForm({ mode: "onChange" })
<FormProvider {...methods}>
  <MyField />
</FormProvider>
```

### Inside Nested Component
```typescript
const { register, watch } = useFormContext()
<input {...register("field")} />
```

### Dynamic Arrays
```typescript
const { fields, append, remove } = useFieldArray({ control, name: "items" })
{fields.map((f, i) => <input {...register(`items.${i}.name`)} />)}
```

### Validation
```typescript
const resolver = async (data) => {
  try {
    const values = await schema.validate(data)
    return { values, errors: {} }
  } catch (e) {
    return { values: {}, errors: { [e.path]: { message: e.message } } }
  }
}
useForm({ resolver })
```

### Watch Specific Field (Efficient)
```typescript
const value = useWatch({ control, name: "singleField" }) // Good
const allData = useWatch({ control }) // Bad - re-renders on every change
```

**Key Principle:** Use `FormProvider` at root, `useFormContext()` in children. No prop drilling!

---

## 2. SUPABASE EDGE FUNCTIONS

### Reusable Database Client
```typescript
let dbInstance = null
export function getDatabase() {
  if (!dbInstance) {
    dbInstance = createClient(...)
  }
  return dbInstance
}
```

### Error Handling
```typescript
try {
  // ... code
} catch (error) {
  if (error instanceof EdgeFunctionError) {
    return new Response(JSON.stringify({ error: error.code }), {
      status: error.statusCode
    })
  }
  console.error(error)
  return new Response(..., { status: 500 })
}
```

### Efficient Queries
```typescript
// Good: Limited, parallel, cached
const [bars, forecast] = await Promise.all([
  supabase.from('ohlc').select('*').eq('symbol', 'AAPL').limit(500),
  supabase.from('ml_forecasts').select('*').eq('symbol', 'AAPL'),
])

// Bad: Unbounded, sequential, no cache
const allBars = await supabase.from('ohlc').select('*')
```

### Response Headers
```typescript
return new Response(JSON.stringify(data), {
  headers: {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Cache-Control": "public, max-age=30", // Cache for 30 seconds
  },
})
```

### Cursor-Based Pagination
```typescript
const query = supabase.from('bars').select('*').limit(500)
if (cursor) query.lt('ts', cursor) // Fetch older
const { data } = await query
const nextCursor = data.length === 500 ? data[data.length-1].ts : null
```

---

## 3. REALTIME SUBSCRIPTIONS

### Simple Subscribe
```typescript
const channel = supabase
  .channel('my-channel')
  .on('postgres_changes',
    { event: 'UPDATE', schema: 'public', table: 'ohlc', filter: 'symbol=eq.AAPL' },
    (payload) => console.log(payload.new)
  )
  .subscribe((status) => {
    console.log(status) // SUBSCRIBED or error
  })
```

### Cleanup
```typescript
useEffect(() => {
  const channel = supabase.channel(...).subscribe()
  return () => supabase.removeChannel(channel) // Cleanup!
}, [supabase])
```

### Buffered Updates (Efficient)
```typescript
const buffer = new Map()
const flush = () => {
  if (buffer.size > 0) {
    onUpdate(Array.from(buffer.values()))
    buffer.clear()
  }
}

// Subscribe
.on('postgres_changes', ..., (payload) => {
  buffer.set(payload.new.id, payload.new)
})

// Flush every 100ms
const interval = setInterval(flush, 100)
return () => clearInterval(interval)
```

### Fallback to Polling
```typescript
// If realtime fails, fall back to polling every 5 seconds
if (realtimeFailed) {
  setInterval(async () => {
    const { data } = await supabase.from('table').select('*').limit(1)
    onUpdate(data[0])
  }, 5000)
}
```

---

## 4. TRADINGVIEW LIGHTWEIGHT CHARTS

### Initialize Chart
```typescript
const chart = createChart(container, {
  width: container.clientWidth,
  height: 500,
  layout: { background: { color: '#1a1a1a' } },
})
const candlestick = chart.addSeries(CandlestickSeries)
```

### Set Historical Data
```typescript
candlestick.setData([
  { time: '2024-01-01', open: 100, high: 105, low: 98, close: 103 },
  // ... more bars
])
chart.timeScale().fitContent()
```

### Real-Time Update (Efficient!)
```typescript
// Good: Update only last bar
candlestick.update({ time: '2024-01-02', open: 103, high: 108, low: 102, close: 107 })

// Bad: Replace entire dataset (slow!)
candlestick.setData([...historicalBars, newBar])
```

### Add Markers (Signals)
```typescript
candlestick.setMarkers([
  { time: '2024-01-02', position: 'belowBar', color: 'blue', shape: 'arrowUp', text: 'Buy' },
  { time: '2024-01-05', position: 'aboveBar', color: 'red', shape: 'arrowDown', text: 'Sell' },
])
```

### Add Price Lines (Support/Resistance)
```typescript
candlestick.createPriceLine({
  price: 100,
  color: '#ff0000',
  lineWidth: 2,
  lineStyle: 1, // Dashed
  title: 'Support Level',
})
```

### Crosshair Legend (For Live Prices)
```typescript
chart.subscribeCrosshairMove((param) => {
  if (param.time) {
    const data = param.seriesData.get(candlestick)
    updateLegend(`${symbol}: ${data.close.toFixed(2)}`)
  }
})
```

### Handle Resize
```typescript
window.addEventListener('resize', () => {
  const rect = container.getBoundingClientRect()
  chart.applyOptions({ width: rect.width, height: rect.height })
})
```

### Cleanup
```typescript
chart.remove() // Clean up canvas
```

---

## PERFORMANCE CHECKLIST

- [ ] Forms use `useFormContext()` (no prop drilling)
- [ ] Edge Functions `.limit()` queries (prevent large datasets)
- [ ] Edge Functions reuse database connection
- [ ] Realtime buffer updates (flush every 100ms)
- [ ] Charts use `.update()` not `.setData()`
- [ ] Charts container has explicit width/height
- [ ] Edge Functions return `Cache-Control` headers
- [ ] No unnecessary `watch()` calls (watch only specific fields)
- [ ] Promise.all() for parallel independent queries
- [ ] Error boundaries around async operations

---

## TROUBLESHOOTING MATRIX

| Issue | Cause | Fix |
|-------|-------|-----|
| `useFormContext is undefined` | Not inside FormProvider | Wrap with `<FormProvider>` |
| Form re-renders everything | Watching entire form | Use `watch("field")` not `watch()` |
| Chart not rendering | No width/height | Add explicit CSS `width: 100%; height: 500px` |
| Chart updates slow | Using `.setData()` | Use `.update()` instead |
| Realtime not working | RLS policy blocks user | Check table RLS allows authenticated |
| Edge Function timeout | Large dataset | Add `.limit(500)` and pagination |
| Market data updates stall | WebSocket closed | Implement polling fallback |
| Chart jumps around | Updating wrong time | Ensure time format consistent (ISO date string) |

---

## FILE LOCATIONS

### Documents
- Full research: `/docs/FRAMEWORK_RESEARCH_2026.md`
- Quick start: `/docs/IMPLEMENTATION_QUICK_START.md`
- This guide: `/docs/QUICK_REFERENCE_CARD.md`
- Navigation: `/docs/FRAMEWORKS_INDEX.md`

### Components to Create
- Forms: `/frontend/src/components/forms/`
- Charts: `/frontend/src/components/TradingViewChart/`
- Hooks: `/frontend/src/hooks/`
- Edge Functions: `/supabase/functions/`

---

## VERSION CHECK (2026)

```bash
# Check your versions
npm list react react-hook-form lightweight-charts @supabase/supabase-js
node --version   # Should be 18+
tsc --version    # Should be 5.3+
```

All code targets:
- React 18.2+
- React Hook Form 7.66+
- lightweight-charts 4.1.3+
- @supabase/supabase-js 2.39.3+

---

## ARCHITECTURE IN 30 SECONDS

```
User Form
  ↓ (FormProvider + useFormContext)
  ├─ Order Entry (DynamicFieldArray)
  ├─ Greeks Display (useWatch)
  └─ Greeks Targets (Controller)

  ↓ onSubmit

  Edge Function (chart-data-v3)
    ├─ Query OHLC (pooled connection)
    ├─ Query Forecast
    ├─ Query Indicators
    └─ Return cached response

  ↓

  TradingView Chart (ChartManager)
    ├─ setData (historical)
    ├─ update (real-time bars)
    └─ setMarkers (signals)

  ↓ (WebSocket)

  Realtime Subscription (useMarketData)
    ├─ Buffer updates
    ├─ Flush every 100ms
    └─ Fallback to polling
```

---

## COPY-PASTE TEMPLATES

### Minimal Form
```typescript
const methods = useForm({ mode: "onChange" })
return (
  <FormProvider {...methods}>
    <form onSubmit={methods.handleSubmit((d) => console.log(d))}>
      <input {...methods.register("field")} />
      <button type="submit">Submit</button>
    </form>
  </FormProvider>
)
```

### Minimal Edge Function
```typescript
serve(async (req) => {
  try {
    const { data, error } = await supabase.from('table').select('*')
    return new Response(JSON.stringify(data), {
      headers: { 'Content-Type': 'application/json', 'Cache-Control': 'max-age=30' }
    })
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500 })
  }
})
```

### Minimal Realtime
```typescript
const channel = supabase.channel('changes').on('postgres_changes',
  { event: 'UPDATE', schema: 'public', table: 'bars' },
  (p) => console.log(p.new)
).subscribe()
```

### Minimal Chart
```typescript
const chart = createChart(container)
const series = chart.addSeries(CandlestickSeries)
series.setData(bars)
series.update(latestBar)
```

---

## OFFICIAL DOCS (Bookmark These)

- React Hook Form: https://react-hook-form.com
- Supabase Realtime: https://supabase.com/docs/guides/realtime
- TradingView LWC: https://tradingview.github.io/lightweight-charts/
- Supabase Functions: https://supabase.com/docs/guides/functions

---

## LAST RESORT: DEBUGGING

```typescript
// Form debugging
console.log(methods.watch()) // Current form state
console.log(methods.formState.errors) // Validation errors

// Chart debugging
console.log(chart.timeScale().getVisibleRange()) // Visible bars
console.log(series.data()) // Current series data

// Realtime debugging
channel.subscribe((status) => console.log('Status:', status))

// Edge Function debugging
console.log('[function-name]', 'Message') // Logs appear in Supabase dashboard
```

---

Print this card. Keep it next to your desk. Reference it for the next 4 weeks.

**You got this!** 🚀
