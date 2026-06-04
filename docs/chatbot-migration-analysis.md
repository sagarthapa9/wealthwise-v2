# WealthWise v2 — Chatbot Migration Analysis

> Why we're moving from v1's raw ReAct loop to a context-injection architecture, and when (and why) we'll add ReAct back.

---

## Table of Contents

1. [What v1 does today](#1-what-v1-does-today)
2. [What the spec demands](#2-what-the-spec-demands)
3. [Context Data Gap Analysis](#3-context-data-gap-analysis--what-the-llm-needs-vs-what-v2-has)
   - 3a. [Personal Context](#3a-personal-context--8-of-13-fields)
   - 3b. [Portfolio Snapshot](#3b-portfolio-snapshot--10-of-12-fields)
   - 3c. [Holdings Classification](#3c-holdings-classification--the-biggest-gap)
   - 3d. [Health Scores](#3d-health-scores--fully-covered)
   - 3e. [Insights](#3e-insights--partially-covered)
   - 3f. [Tax Summary](#3f-tax-summary--6-of-7-fields)
   - 3g. [Benchmark](#3g-benchmark--not-built)
4. [The migration decision: context-first then ReAct](#4-the-migration-decision-context-first-then-react)
5. [Architecture: v2 Phase 1 (now) — Context Injection](#5-architecture-v2-phase-1-now--context-injection)
6. [Architecture: v2 Phase 2 (later) — + ReAct Loop](#6-architecture-v2-phase-2-later--react-loop)
7. [When to add ReAct — decision triggers](#7-when-to-add-react--decision-triggers)
8. [Scenarios where ReAct earns its keep](#8-scenarios-where-react-earns-its-keep)
9. [Comparison: v1 raw loop vs v2 context-injection vs v2 ReAct](#9-comparison-v1-raw-loop-vs-v2-context-injection-vs-v2-react)
10. [What was considered and rejected](#10-what-was-considered-and-rejected)

---

## 1. What v1 does today

`chatBot_dpsk.py` implements a ReAct-style agent loop:

```
User message
      │
      ▼
System prompt = prompt_manager.get_prompt() + appended portfolio_context STRING
      │
      ▼
LLM call (DeepSeek reasoner) with tools=[get_weather, get_user_data, analyze_ticker]
      │
      ├── [no tool_calls] → return response
      │
      └── [tool_calls] → _handle_function_calls()
              │
              ├── Execute each tool via hardcoded if/elif
              ├── Append results to conversation history
              └── Second LLM call → return response
```

**What works well:**
- Tool calling pattern is correct — LLM decides if it needs tools, not hardcoded
- Reasoning content is captured and persisted
- Conversation memory is persistent (SQLite)

**What needs fixing for v2:**
- Portfolio context is a raw string appended to the system prompt — no structure
- No context builder — relies on `FundAnalysisFunctions.get_user_data()` returning hardcoded mock data
- Tool dispatch is an if/elif chain — not extensible
- SQLite persistence — not suitable for web deployment
- Tightly coupled to Streamlit's session state

---

## 2. What the spec demands

The spec (`wealthwise_llm_analysis_engine.md`) defines:

| Component | Purpose | Status in v1 | Status in v2 |
|-----------|---------|-------------|-------------|
| `LLMPortfolioContext` JSON payload | Structured portfolio data for LLM | ❌ Appended string | ❌ To be built |
| System prompt template | Response format + hard rules + UK terms | Partial | ❌ To be built |
| Context builder | Assembles context from DB | ❌ Uses hardcoded `get_user_data()` | ❌ To be built (services exist) |
| Health scores in context | 5-dimension health scoring | ✅ In v1 lib/ | ✅ Already migrated to v2 services/ |
| Insights in context | 7 detectors → RawInsight | ✅ In v1 lib/ | ✅ Already migrated to v2 services/ |
| Hook templates | Tab-specific AI questions | ✅ In v1 lib/ | ✅ Already migrated to v2 services/ |
| Response validation | WHAT/WHY/ACTION check | ❌ Not implemented | ⏸️ Deferred |
| Guardrails | Hard blockers + UK terms | ❌ Not implemented | To be built |
| Session memory | Compound learning across sessions | ✅ Basic (SQLite) | To be built (PostgreSQL) |
| Chat UI | Chat interface | ✅ Streamlit | ❌ To be built (React) |

---

## 3. Context Data Gap Analysis — What the LLM Needs vs What v2 Has

Before building the context builder, we need to know: does v2 actually store the data the `LLMPortfolioContext` requires? Answer: **not yet for critical fields.**

### 3a. Personal Context — 8 of 13 fields

| Spec field | v2 source | Status |
|-----------|-----------|--------|
| `age` | `profiles.age` | ✅ |
| `risk_tolerance` | `profiles.risk_tolerance` | ✅ |
| `investment_horizon_years` | `profiles.investment_horizon` — free text, not a number | ⚠️ Needs conversion |
| `goal` | `profiles.primary_goal` | ✅ |
| `tax_band` | `profiles.tax_band` | ✅ |
| `pension_contributions_monthly` | `profiles.pension_contributions_monthly` | ✅ |
| `isa_contributions_monthly` | `profiles.isa_contributions_monthly` | ✅ |
| `country: "UK"` | Hardcoded | ✅ |
| `monthly_savings` | **Not stored** | ❌ |
| `retirement_age_target` | **Not stored** | ❌ |
| `employment_status` | **Not stored** | ❌ |
| `dependents` | **Not stored** | ❌ |
| `mortgage_remaining` | **Not stored** | ❌ |
| `annual_income` | **Not stored** | ❌ |

**Impact:** Low. The LLM can work without these — it just says "I don't know your savings rate" for retirement projections. Add incrementally as users request that analysis.

### 3b. Portfolio Snapshot — 10 of 12 fields

| Spec field | v2 source | Status |
|-----------|-----------|--------|
| `total_value_gbp`, `total_cost_gbp`, `total_gain_gbp`, `total_gain_pct` | `PortfolioData` computed properties | ✅ |
| `equity_pct`, `fixed_income_pct`, `cash_pct`, `property_pct` | `compute_asset_class_allocation()` | ✅ Computable |
| `commodity_pct` | **Not tracked** — no "commodity" in asset_class enum | ❌ |
| `multi_asset_pct` | "alternative" buckets multi-asset funds | ⚠️ Approximate |
| `weighted_ocf` | **Not stored** — no `ocf_pct` on holdings | ❌ |
| `num_holdings`, `num_accounts` | Direct count from data | ✅ |

**Critical gap:** `weighted_ocf` — the LLM can't answer "am I paying too much in fees?" without OCF data. Needs `ocf_pct` on every holding.

### 3c. Holdings Classification — THE BIGGEST GAP

**This is the critical problem.** The spec requires per-holding `type`, `asset_class`, `sector`, and `geography` — but v2 currently **infers** these from hardcoded ticker-prefix matching in `allocations.py`:

```python
# Current approach — hardcoded guesses that fail for unknown tickers
def _infer_sector(ticker, asset_class):
    if ticker.startswith("VWRL") or ticker.startswith("VWRP"): return "global_diversified"
    if ticker.startswith("VUAG"): return "us_large_cap"
    return "global_diversified"  # ← EVERY unknown ticker gets this wrong label
```

**The fix:** yfinance already returns this data for free at search time:

```python
info = yf.Ticker("VWRL.L").info
# {
#   "legalType": "Exchange Traded Fund",      → maps to type="ETF"
#   "category": "Global Large-Stock Blend",   → maps to asset_class="equity", sector="global_diversified"
#   "country": "Global",                       → maps to geography="global"
#   "annualReportExpenseRatio": 0.0022,       → ocf_pct
#   "yield": 0.0174,                          → dividend_yield_pct
#   "isin": "IE00B3RBWM25",                   → isin
# }
```

All that's needed: (1) save these fields at holding-creation time, (2) a classification mapping table to translate yfinance categories → spec categories. No extra user input required.

### 3d. Health Scores — fully covered

`health_score.py` is already migrated and produces the exact structure the spec needs:
`{ overall, grade, dimensions: [{name, score, weight, detail}], top_findings }`

### 3e. Insights — partially covered

The 7 insight detectors (`insight_engine.py`) produce `RawInsight` objects. Converting to the spec's `Insight` shape with `severity`, `title`, `detail`, `prompt` needs a thin adapter — the data is there, just needs reshaping.

### 3f. Tax Summary — 6 of 7 fields

All computable from accounts + holdings + profile **except** `gia_dividend_income_estimate` which needs `dividend_yield_pct` on holdings. Fixing the holding data gap (3c) closes this.

### 3g. Benchmark — not built

Spec marks this as `nullable`. Deferred until historical portfolio snapshots exist.

### Summary: Ready vs Gap

```
personal           ████████░░  8/13  (missing fields are low-priority)
portfolio_snapshot  █████████░  10/12 (weighted_ocf needs ocf_pct on holdings)
holdings per item   ██████░░░░  9/16  (CRITICAL: classification is hardcoded guesses)
health_scores       ██████████  5/5   ✓
insights            ███████░░░  4/5   (thin adapter needed)
tax_summary         ████████░░  6/7   (needs dividend_yield_pct from 3c fix)
benchmark           ░░░░░░░░░░  0/5   (nullable, deferred)
```

**Bottom line:** Fix holding classification (3c) and everything else becomes computable. The fix needs no new user inputs — just save what yfinance already returns.

---

## 4. The migration decision: context-first then ReAct

### The key insight

**Analysis of the spec's capabilities matrix (§4) shows ~95% of questions are answerable from portfolio context alone:**

| Analysis type | Example question | Data needed | Tool calls |
|--------------|-----------------|-------------|------------|
| Risk | "Am I too risky?" | equity_pct, risk_tolerance, age | 0 |
| Diversification | "Am I diversified enough?" | holdings[], sector, geography | 0 |
| Tax efficiency | "Should I use my ISA?" | isa_allowance_remaining, tax_band | 0 |
| Cost | "Am I paying too much?" | holdings[].ocf_pct, weighted_ocf | 0 |
| Cash | "Too much cash?" | cash_pct, total_cash | 0 |
| Goals | "On track for retirement?" | age, portfolio_value, savings_rate | 0 |
| Stress testing | "What if markets crash?" | equity_pct, fixed_income_pct | 0 |
| Ticker price | "What's VWRL at now?" | ticker symbol | **1** |

The only scenario requiring tools is live market data. Everything else is in the context payload.

### Decision

**Phase 1 (now): Context injection** — Build the context builder + system prompt + chat endpoint. LLM receives everything upfront. Optional single tool call for `analyze_ticker` only. This delivers 90% of the spec's value with ~50% of the complexity.

**Phase 2 (later): + ReAct loop** — Add multi-step tool orchestration when WealthWise needs capabilities that require exploration: fund replacement research, constraint-solving rebalancing, tax year-end optimisation, web search integration.

---

## 5. Architecture: v2 Phase 1 (now) — Context Injection

```
User adds holdings + profile (✔ already built)
         │
         ▼
User clicks "Analyze Portfolio" (✔ already built)
         │
         ▼
POST /api/v1/chat  { message, session_id }
         │
         ▼
ChatService.chat()
  ├── 1. Check guardrails (hard blockers: "execute trade", "place order")
  ├── 2. Build LLMPortfolioContext from DB:
  │      ├── profile → personal context
  │      ├── accounts + holdings → portfolio_snapshot + accounts breakdown
  │      ├── health_score.py → health_scores
  │      ├── insight_engine.py → insights (top 4)
  │      └── tax_summary (computed from holdings + wrappers)
  ├── 3. Build system prompt:
  │      ├── Master template (rules, UK terms, WHAT/WHY/ACTION format)
  │      ├── Portfolio context JSON
  │      ├── Health scores text
  │      └── Personal context variables
  ├── 4. Call DeepSeek with:
  │      ├── System prompt (context-rich, ~1,560 tokens)
  │      ├── Conversation history (from DB)
  │      └── Tools: [analyze_ticker] only
  ├── 5. If LLM returns tool_calls → execute → second LLM call
  ├── 6. Persist all messages to PostgreSQL
  └── 7. Return JSON response { message, reasoning_content, session_id }
         │
         ▼
Frontend: ChatPanel renders response + collapsible "💭 AI Thinking"
```

### What this architecture enables

| User action | What happens |
|------------|--------------|
| Click "Analyze Portfolio" | LLM gets first-interaction prompt (spec §9.1) → "Your portfolio is £X. Health: C. Biggest issue: 91% equities..." |
| Tap "Ask AI" on an insight card | LLM receives pre-built question + insight context → answers using portfolio numbers |
| Type "Am I diversified?" | LLM reads equity_pct, sector%, geography% from context → "You have 12 holdings. 91% is equities. 45% in one global fund..." |
| Type "What's VWRL at?" | LLM calls `analyze_ticker("VWRL")` → returns live price |
| Type "Execute a trade" | Guardrail blocks → returns refusal |

### What this architecture does NOT do (yet)

- ❌ Multi-step research ("find me 3 cheaper alternatives to my active funds")
- ❌ Constraint-solving rebalancing ("rebalance to 70% equity without triggering CGT")
- ❌ Web search ("how will dividend tax changes affect my GIA?")
- ❌ Cross-session compound learning (the LLM remembering your portfolio from last month)

These require ReAct-style exploration — the LLM doesn't know what it needs until it's gathered some data.

---

## 6. Architecture: v2 Phase 2 (later) — + ReAct Loop

When the triggers in §6 fire, the chat service gains a while-loop:

```
ChatService.chat()
  ├── 1-3. Same as Phase 1 (guardrails → context → system prompt)
  │
  ├── 4. ReAct loop (new):
  │      │
  │      ▼
  │   LLM call with tools
  │      │
  │      ├── [no tool_calls] → exit loop → format response
  │      │
  │      └── [tool_calls] → execute all → append to history
  │              │
  │              ├── analyze_ticker("VWRP")  → OCF, sector, performance
  │              ├── search_etfs(criteria)    → matching ETFs
  │              ├── calculate_tax_impact()   → CGT/pension relief
  │              └── search_web(query)        → HMRC rules, market news
  │              │
  │              ▼
  │         Second LLM call (now has research results)
  │              │
  │              ├── [no tool_calls] → exit
  │              └── [more tool_calls] → continue (max 5 iterations)
  │
  ├── 5. Persist + return
```

The only difference from Phase 1: step 4 becomes a loop instead of a single if/else. Same endpoints, same frontend, same context builder. The loop is purely an internal upgrade.

---

## 7. When to add ReAct — decision triggers

Don't add the loop until one of these is true:

| Trigger | Signal | Example |
|---------|--------|---------|
| **Incomplete answers** | LLM frequently says "I can't tell from your portfolio data, you'd need to look up..." | User asks "find cheaper ETFs" → LLM can't without search |
| **New tool added** | You add a second tool beyond `analyze_ticker` that returns data the LLM needs to cross-reference | Adding `search_etfs` + `calculate_tax_impact` → LLM needs both to answer |
| **Web search integration** | User asks questions about current events, tax changes, market conditions | "Did the UK budget change dividend tax?" |
| **Constraint-solving demand** | Users want exact rebalancing plans, not general advice | "Exactly what to sell and buy to hit 70% equity without triggering CGT" |

Adding ReAct before these triggers fire is premature — you'd be maintaining a loop that executes 0-1 iterations in 95% of conversations.

---

## 8. Scenarios where ReAct earns its keep

### Fund replacement research

```
User: "Replace my active funds with cheaper passive ETFs."

ReAct loop (3-5 iterations):
  1. LLM reads context → identifies 3 active funds
  2. LLM calls search_etfs("global equity tracker", max_ocf=0.2) → gets 8 ETFs
  3. LLM calls analyze_ticker() on top 3 matches → compares OCF, tracking error
  4. LLM calls search_etfs("global bond tracker hedged") → gets 5 ETFs
  5. LLM synthesises: "Replace Global Equity Fund with VWRP (OCF 0.22% vs 0.45%)"
```

### Rebalancing with tax constraints

```
User: "Get me to 70% equity without selling anything in my SIPP."

ReAct loop (3-4 iterations):
  1. LLM reads context → current equity 91%, target 70%, accounts breakdown
  2. LLM computes sell targets → checks CGT exposure in GIA
  3. LLM realises one sale exceeds CGT allowance → adjusts plan
  4. LLM proposes: "Sell £5k VUSA in ISA (no CGT), buy £5k VAGP bonds..."
```

### Tax year-end optimisation

```
User: "Tax year ends in 2 months. I have £15k cash. ISA, SIPP, or mortgage?"

ReAct loop (4-5 iterations):
  1. LLM reads personal context → higher rate taxpayer, age 38, £120k mortgage
  2. LLM reads tax_summary → ISA: £5k/£20k used, SIPP: £400/mo
  3. LLM calls calculate_tax_impact(15000, "ISA") → tax-free growth, no relief
  4. LLM calls calculate_tax_impact(15000, "SIPP") → £3,750 relief, locked until 57
  5. LLM calls calculate_tax_impact(15000, "mortgage") → saves £480/yr interest
  6. LLM notices age 38 → LISA available until 40 → suggests £4k LISA + split remainder
```

### Multi-source research (when web search is added)

```
User: "Will the dividend tax changes affect my GIA?"

ReAct loop (3-4 iterations):
  1. LLM calls search_web("UK dividend tax allowance 2026/27") → reads HMRC page
  2. LLM reads context → GIA dividend estimate: £1,200/yr
  3. LLM calculates: £1,200 - £500 allowance = £700 taxable at 33.75%
  4. LLM calls search_web("accumulation units dividend tax") → finds deferral strategy
  5. LLM answers: "£236 tax bill. Switch to accumulation units or move to ISA."
```

### The common pattern

Every scenario follows the same shape: **the LLM discovers information mid-analysis that changes what it asks next.** This is fundamentally different from context-injection where the LLM has all the data upfront.

---

## 9. Comparison: v1 raw loop vs v2 context-injection vs v2 ReAct

| | v1 Raw Loop | v2 Context Injection (now) | v2 + ReAct (later) |
|---|---|---|---|
| **Context** | Appended string | Structured `LLMPortfolioContext` JSON | Same |
| **System prompt** | File-based templates | Spec template + injected variables | Same |
| **Tool dispatch** | Hardcoded if/elif | Single inline if (analyze_ticker) | Registry with while-loop |
| **Tools available** | get_weather, get_user_data, analyze_ticker | analyze_ticker only | analyze_ticker + search_etfs + tax_calc + search_web |
| **Loop iterations** | 0-1 (single if tool_calls) | 0-1 (single if tool_calls) | 0-5 (while tool_calls) |
| **Response format** | Raw text | JSON with reasoning_content | Same |
| **Persistence** | SQLite (sync) | PostgreSQL (async) | Same |
| **Frontend** | Streamlit | React + Vite | Same |
| **SSE streaming** | No | No (deferred) | Yes |
| **Guardrails** | No | Hard blockers + UK terms | Same |
| **Use cases covered** | Basic chat + weather + mock portfolio | 95% of spec analysis capabilities | 100% + fund research + rebalancing + web search |

---

## 10. What was considered and rejected

### Rejected: Full ReAct loop from day one

**Why rejected:** The spec's own analysis matrix shows 95% of questions don't need tool calls. Adding a while-loop for the 5% case means:

- More complex error handling (infinite loop guard, timeout management)
- More expensive (each loop iteration burns 2k+ tokens on the system prompt)
- Harder to debug (you're stepping through 3-5 LLM calls, not 1-2)
- No user benefit for the common case

**When to reconsider:** When a new tool (beyond `analyze_ticker`) is added that returns data the LLM needs to cross-reference with other tools.

### Rejected: SSE streaming in v1 of the migration

**Why rejected:** SSE adds complexity across the stack (FastAPI `StreamingResponse`, `EventSource` in React, partial-token state management) for a UX improvement (seeing tokens appear). The v1 Streamlit app didn't stream, and users were fine with it.

**When to add:** After the chat UI is stable and users are actively using it. Stream the LLM response and `reasoning_content` as two parallel event streams.

### Rejected: Response validator (regex-based)

**Why rejected:** Extracting numbers from LLM output to validate they match portfolio values is fragile. False positives on edge cases (e.g., the LLM references £20,000 ISA allowance, which happens to match a holding value) would frustrate users. With a good system prompt and `deepseek-reasoner`, the model naturally references user numbers.

**When to add:** Only if quality audits show >10% of responses are generic/non-specific to the user's portfolio.

### Rejected: LangGraph

**Why rejected:** LangGraph solves multi-agent routing and state-machine checkpointing. WealthWise is a single-agent chatbot. Adding LangGraph would mean:
- A heavy dependency for no current benefit
- Debugging framework abstractions instead of your own code
- Constrained by the graph model when a simple loop works

**When to reconsider:** If you need: (a) different agents for different query types, (b) human-in-the-loop approval for certain actions, or (c) complex branching logic that's painful in raw code.

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WEALTHWISE CHATBOT EVOLUTION                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  NOW (Phase 1)                   LATER (Phase 2)                    │
│  ┌─────────────────────┐        ┌─────────────────────────┐        │
│  │ Context Injection   │        │ + ReAct Loop            │        │
│  │                     │        │                         │        │
│  │ • Structured JSON   │        │ • While tool_calls      │        │
│  │   context payload   │        │ • Multi-step research   │        │
│  │ • Spec system prompt│        │ • Constraint solving    │        │
│  │ • Single tool call  │        │ • Web search            │        │
│  │   (analyze_ticker)  │        │ • Fund comparisons      │        │
│  │ • PostgreSQL memory │        │ • Tax calculations      │        │
│  │ • React chat UI     │        │ • SSE streaming         │        │
│  │                     │        │                         │        │
│  │ Covers: 90% of spec │        │ Covers: 100% of spec    │        │
│  └─────────────────────┘        └─────────────────────────┘        │
│                                                                     │
│  Trigger for Phase 2:                                               │
│  "The LLM gives incomplete answers because it needs data            │
│   it doesn't have yet, and getting that data changes                │
│   what it asks for next."                                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```
