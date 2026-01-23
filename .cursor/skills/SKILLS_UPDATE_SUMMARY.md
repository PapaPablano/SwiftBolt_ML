# Skills Update Summary

**Date:** Friday, January 23, 2026
**Status:** ✅ Complete

## Overview

All skills have been updated with:
1. **Location headers** pointing to their absolute file paths
2. **MCP tool integration** documentation (where applicable)
3. **Research skill** completely rewritten for Perplexity MCP alignment + trading/ML playbook

---

## Updated Skills

### 1. ✅ agent-setup.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/agent-setup.mdc`

**Changes:**
- Added explicit `**Location:**` header
- Documented MCP file system tools integration:
  - `mcp_tool_8_list_directory` – Project navigation
  - `mcp_tool_2_read_text_file` – File reading
  - `mcp_tool_6_edit_file` – Code modifications
  - `mcp_tool_5_write_file` – File creation
  - `mcp_tool_12_search_files` – Pattern searching
- Added workflow diagram and best practices

---

### 2. ✅ dataset-engineering.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/dataset-engineering.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved comprehensive dataset creation, cleaning, and augmentation guidance
- Ready for use with LLM fine-tuning and ML pipelines

---

### 3. ✅ frontend-design.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/frontend-design.mdc`

**Changes:**
- Added heading and `**Location:**` header
- Preserved aesthetic-driven UI/UX design guidance
- Focus on avoiding "AI slop" with bold design directions

---

### 4. ✅ gitactions.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/gitactions.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved CI/CD workflow templates
- Production-ready GitHub Actions patterns maintained

---

### 5. ✅ ml-pipeline-workflow.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/ml-pipeline-workflow.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved end-to-end MLOps orchestration guidance
- DAG patterns, data preparation, model validation, deployment strategies intact

---

### 6. ✅ options.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/options.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved comprehensive options trading strategies with Alpaca integration
- All 7 phases of options expertise (fundamentals through governance) maintained
- Risk management checklist and strategy decision matrix intact

---

### 7. ✅ sql-optimization-patterns.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/sql-optimization-patterns.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved SQL query optimization and indexing strategies
- EXPLAIN analysis and performance tuning patterns maintained

---

### 8. ✅ ui-ux-pro-max.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/ui-ux-pro-max.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved design intelligence database (UI styles, color palettes, typography, UX guidelines)
- Stack-specific best practices maintained

---

### 9. ✅ weights-and-biases.mdc
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/weights-and-biases.mdc`

**Changes:**
- Added `**Location:**` header
- Preserved comprehensive W&B experiment tracking, hyperparameter sweeps, artifacts, and integrations
- Team collaboration features and pricing guide maintained

---

### 10. 🎯 research-lookup/research.mdc (MAJOR REWRITE)
**Location:** `/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/research-lookup/research.mdc`

**COMPLETE REWRITE - Perplexity MCP Alignment + Trading/ML Playbook**

#### Key Changes:

**1. Perplexity MCP Tools (Replaces OpenRouter/Sonar)**
- `search_web` – Keyword-based internet search (1–3 queries per call)
- `get_url_content` – Deep read/summarize specific URLs, PDFs, documentation
- `search_pplx_support` – Perplexity help center lookup for platform-specific questions
- **Citation discipline:** Every externally-derived sentence must include `[web:x]`, `[page:x]`, or `[support:x]`

**2. Research Modes**
- **Snapshot Mode** – Quick lookup (1 search, ~10s)
- **Deep Dive Mode** – Comprehensive research (3 searches + URL content, ~30s)
- **Audit Mode** – Fact-checking and validation

**3. MCP Tool Decision Tree**
- Time-sensitive questions → `search_web`
- 3rd-party APIs/tools → `search_web`
- Perplexity-specific → `search_pplx_support`
- Deep document extraction → `get_url_content`

**4. Trading & ML Research Playbook**

Concrete research workflows tailored to SwiftBolt_ML stack:

- **Alpaca API & Market Data** – Latest API updates, rate limits, options Greeks
- **ML Models for Stock Prediction** – Transformer vs LSTM, attention mechanisms, multi-timeframe learning
- **Options Pricing & Greeks** – Black-Scholes, IV surface, exotic options, automatic differentiation
- **Volatility Modeling** – GARCH, IV rank/percentile, machine learning approaches
- **Technical Analysis Indicators** – ML-enhanced KDJ, RSI, MACD, backtesting validation
- **Data Quality & Feature Engineering** – Preprocessing, outlier detection, normalization, gap handling
- **Regulatory & Compliance** – SEC/FINRA rules, algorithmic trading requirements
- **Libraries & Tools Comparison** – PyTorch vs TensorFlow, Alpaca vs Polygon vs Finnhub

**5. Query Template Library**

Copy-paste ready search queries organized by domain:
- Alpaca & trading infrastructure
- ML & forecasting
- Options & Greeks
- Technical analysis
- Data & features

**6. Advanced Patterns**
- Multi-step research (breadth → depth → implementation)
- Comparative deep dives
- Validation/fact-checking workflows

**7. Error Handling & Fallbacks**
- What to do if search returns no results
- URL unavailable handling
- Perplexity-specific question fallbacks
- Never hallucinate sources

**8. Citation Best Practices**
- Inline citations immediately after facts
- Sequential numbering
- Mix sources naturally
- Always provide URLs for user follow-up

**9. Integration Notes**
- Pairs with options.mdc, ml-pipeline-workflow.mdc, dataset-engineering.mdc, weights-and-biases.mdc

---

## File Locations

All skills are centralized in:
```
/Users/ericpeterson/SwiftBolt_ML/.cursor/skills/
├── agent-setup.mdc
├── dataset-engineering.mdc
├── frontend-design.mdc
├── gitactions.mdc
├── ml-pipeline-workflow.mdc
├── options.mdc
├── sql-optimization-patterns.mdc
├── ui-ux-pro-max.mdc
├── weights-and-biases.mdc
└── research-lookup/
    ├── research.mdc [MAJOR REWRITE]
    ├── research_lookup.py
    ├── lookup.py
    ├── examples.py
    ├── README.md
    └── scripts/
```

---

## Perplexity MCP Integration Summary

### Tools Now Explicitly Wired

| Tool | Purpose | Citation Format |
|------|---------|------------------|
| `search_web` | Internet search (current facts, rankings, APIs, docs) | `[web:x]` |
| `get_url_content` | Deep read PDFs/long docs/specifications | `[page:x]` |
| `search_pplx_support` | Perplexity help center (subscriptions, Labs, Comet, Spaces) | `[support:x]` |

### Citation Discipline

✅ **MANDATORY:** Every externally-derived sentence must include inline citation.

```
❌ BAD:  "Alpaca API supports multi-leg options orders."
✅ GOOD: "Alpaca API supports multi-leg options orders[web:1]."
```

### Research Workflow

```
Question → Assess time-sensitivity
         → Choose mode (Snapshot/Deep Dive/Audit)
         → Execute search(es) with `search_web` or `search_pplx_support`
         → Optional: Extract details with `get_url_content`
         → Synthesize with citations
         → Provide URLs for user follow-up
```

---

## Quick Usage Guide

### When to Use `search_web` (Research Skill)
- "What's new with Alpaca's options API in 2026?"
- "Latest transformer architectures for time-series?"
- "How do I calculate Greeks with automatic differentiation?"
- "Alpaca vs Polygon vs Finnhub comparison?"
- "Best practices for backtesting technical indicators?"

### When to Use `search_pplx_support` (Research Skill)
- "What is Perplexity Labs?"
- "How do I upgrade to Perplexity Pro?"
- "What is Comet?"
- "How do I create Spaces?"

### When to Use `get_url_content` (Research Skill)
- After `search_web`, to extract full content from:
  - arXiv papers (PDF)
  - Technical documentation
  - Academic whitepapers
  - Long blog posts with detailed specs

---

## Next Steps

1. **Verify Location Headers** – Check that all skills show correct paths
2. **Test Research Workflows** – Try queries from the trading/ML playbook
3. **Customize Queries** – Adapt templates for your specific use cases
4. **Bookmark Resources** – Note key research sources from playbook
5. **Extend Playbook** – Add domain-specific queries as you discover patterns

---

## Files Modified

```
10 total files updated:
✅ agent-setup.mdc
✅ dataset-engineering.mdc
✅ frontend-design.mdc
✅ gitactions.mdc
✅ ml-pipeline-workflow.mdc
✅ options.mdc
✅ sql-optimization-patterns.mdc
✅ ui-ux-pro-max.mdc
✅ weights-and-biases.mdc
✅ research-lookup/research.mdc (MAJOR REWRITE)

+ Created: SKILLS_UPDATE_SUMMARY.md (this file)
```

---

## Support

All skills now include:
- Explicit file locations for easy reference
- Clear MCP tool documentation
- Citation discipline guidelines
- Trading/ML-specific playbooks and query templates
- Error handling strategies
- Integration notes with other skills

For questions about specific skills or workflows, refer to the detailed sections in each skill file.
