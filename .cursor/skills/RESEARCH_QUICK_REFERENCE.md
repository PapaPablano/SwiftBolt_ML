# Research Skill Quick Reference

**File:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/research-lookup/research.mdc`

## Three MCP Tools

```
┌─────────────────────────────────────────────────────────┐
│ search_web                                              │
├─────────────────────────────────────────────────────────┤
│ Use for: current facts, APIs, rankings, stats           │
│ Returns: snippets + URLs                                │
│ Citation: [web:1], [web:2]                             │
│ Queries per call: 1–3 (keep focused)                   │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ get_url_content                                         │
├─────────────────────────────────────────────────────────┤
│ Use for: PDFs, long docs, specs, papers                │
│ Input: URL or file path                                │
│ Returns: full content summary                          │
│ Citation: [page:1], [page:2]                           │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ search_pplx_support                                     │
├─────────────────────────────────────────────────────────┤
│ Use for: Perplexity features, Labs, Comet, Spaces      │
│ Returns: help center articles                          │
│ Citation: [support:1], [support:2]                     │
└─────────────────────────────────────────────────────────┘
```

---

## Three Research Modes

### 🏃 Snapshot Mode (Quick Lookup)
```
1 search_web query → Top results → Cite → Done
Time: ~10 seconds

Example: "Alpaca API rate limits 2026"
```

### 🔍 Deep Dive Mode (Comprehensive)
```
3 search_web queries:
  1. Breadth (overview)
  2. Depth (specifics/benchmarks)
  3. Implementation (how-to/code)
→ get_url_content on top 1–3 URLs
→ Synthesize with multiple citations
Time: ~30 seconds

Example queries:
  1. "transformer time-series forecasting 2024"
  2. "LSTM vs transformer benchmark stock"
  3. "attention implementation PyTorch"
```

### ✅ Audit Mode (Fact-Checking)
```
Claim: "X is the best for Y"
→ search_web to find current sources
→ Compare against your knowledge
→ Flag conflicts or outdated info
→ Cite latest as ground truth
```

---

## Citation Rules (MANDATORY)

✅ **ALWAYS add citations:**
```
Fact here[web:1].
AnotherFact[page:2].
Perlexity feature[support:3].
Mixed sources[web:1][page:2].
```

❌ **NEVER cite without source:**
```
Fact here.  ← NO! Add [web:x]
Claim made up.  ← NO! Search first!
```

---

## Trading & ML Playbook Queries

### Alpaca Trading
```
"Alpaca API [feature] latest update 2026"
"Alpaca options Greeks real-time streaming"
"Alpaca vs Polygon data API comparison"
```

### ML Forecasting
```
"transformer attention time-series stock price 2024"
"LSTM vs transformer financial forecasting benchmark"
"multi-timeframe attention mechanism implementation"
```

### Options & Greeks
```
"Black-Scholes Greeks numerical stability automatic differentiation"
"IV surface interpolation options Greeks calculation"
"exotic options Greeks computation methods"
```

### Volatility
```
"implied volatility forecasting GARCH 2024"
"IV rank IV percentile calculation methodology"
"volatility surface machine learning prediction"
```

### Technical Analysis
```
"machine learning KDJ RSI enhancement 2024"
"technical indicator backtesting walk-forward validation"
"overfitting detection technical analysis indicators"
```

### Data Prep
```
"financial time-series outlier detection preprocessing"
"feature engineering stock market data normalization"
"handling missing data gaps financial datasets"
```

---

## Decision Tree (Which Tool?)

```
Question
  ↓
  Is it time-sensitive (2024+, "latest", "current")?
  ├─ YES → use search_web
  └─ NO → Is it about a 3rd-party API/tool?
          ├─ YES → use search_web
          └─ NO → Is it about Perplexity itself?
                  ├─ YES → use search_pplx_support
                  └─ NO → Can I answer from training? If unsure → search_web

Do I need deep extraction (PDF, long doc, full spec)?
  ├─ YES → use get_url_content after search_web
  └─ NO → Use search_web snippets directly
```

---

## Error Handling

| Problem | Solution |
|---------|----------|
| No search results | Rephrase query, try different keywords, broaden scope |
| URL unavailable | Try another URL from results, use snippet instead, note in response |
| Perplexity question fails | Fall back to `search_web` with "Perplexity [question]" |
| Can't find info after search | Say "I searched and didn't find X", don't hallucinate |

---

## Citation Format Examples

### Single source
```
Alpaca's paper trading is commission-free[web:1].
```

### Multiple sources
```
Alpaca API rate limit is 200 requests/min[web:1]. 
Optional strategy is to batch requests[page:2].
```

### With direct quote
```
According to Alpaca docs[page:1], "Multi-leg orders are
supported via the OTO order class."
```

### Perplexity-specific
```
Perplexity Pro offers advanced AI[support:1].
Perplexity Labs provides experimental features[support:2].
```

---

## Best Practices

✅ Search before claiming current info
✅ Use 1–3 focused queries (not rambling)
✅ Citation immediately after fact
✅ Include URLs for user follow-up
✅ Synthesize across sources
✅ Note when info conflicts

❌ Assume training data is current
❌ Send vague or overly broad searches
❌ Forget citations
❌ Hide sources
❌ Hallucinate papers/research

---

## Integration with Other Skills

- **options.mdc** → Research latest Greeks, volatility models, strategy updates
- **ml-pipeline-workflow.mdc** → Research data pipelines, backtesting frameworks
- **dataset-engineering.mdc** → Research data formats, cleaning methods
- **weights-and-biases.mdc** → Research W&B features, experiment tracking best practices

---

## Example: Full Deep Dive Workflow

**Question:** "How do I implement attention-based volatility forecasting?"

**Step 1: Multi-Query Search**
```
Query 1: "attention mechanism volatility forecasting 2024" → landscape
Query 2: "volatility GARCH attention transformer implementation" → specifics
Query 3: "PyTorch attention layer volatility prediction" → how-to
```

**Step 2: Extract from Promising URLs**
```
get_url_content on:
  - Top GitHub repo with working code
  - Academic paper with methodology
```

**Step 3: Synthesize with Citations**
```
Attention mechanisms have been applied to volatility[web:1].
The transformer architecture is detailed in [page:1].
PyTorch implementation example from [page:2] shows...
Recent benchmarks[web:2] demonstrate X% improvement.
```

**Step 4: Provide URLs**
```
Full paper: [link]
GitHub repo: [link]
Blog post: [link]
```

---

## Pro Tips

💡 **Tip 1:** For API questions, always search—APIs change constantly

💡 **Tip 2:** For "best X" questions, Deep Dive mode finds actual comparisons with data

💡 **Tip 3:** Use Audit mode when you have a hypothesis—search might validate or flip it

💡 **Tip 4:** Copy-paste query templates from playbook and customize

💡 **Tip 5:** When stuck, break multi-part question into 3 separate searches

---

## See Full Documentation

📖 **Complete Research Skill:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/research-lookup/research.mdc`

Includes:
- 9 trading/ML research playbook sections
- Query template library
- Advanced patterns (multi-step, comparative, validation)
- Full error handling guide
- Integration notes
