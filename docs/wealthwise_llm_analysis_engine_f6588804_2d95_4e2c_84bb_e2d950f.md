# Wealthwise — LLM Analysis Engine Spec

> What data we feed the LLM, what we ask it to analyse, and how we structure prompts for best results.
> For developers and prompt engineers. Last updated: 4 June 2026.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [The Portfolio Context Payload](#2-the-portfolio-context-payload)
3. [System Prompt Architecture](#3-system-prompt-architecture)
4. [Analysis Capabilities — What the LLM Does](#4-analysis-capabilities--what-the-llm-does)
5. [Response Format Enforcement](#5-response-format-enforcement)
6. [Memory — The Core Moat](#6-memory--the-core-moat)
7. [Session Memory Schema](#7-session-memory-schema)
8. [Guardrails & Constraints](#8-guardrails--constraints)
9. [Prompt Templates per Scenario](#9-prompt-templates-per-scenario)
10. [Cost & Token Budget](#10-cost--token-budget)
11. [Testing & Quality Framework](#11-testing--quality-framework)
12. [Future: Multi-User & Shared Portfolios](#12-future-multi-user--shared-portfolios)

---

## 1. Architecture Overview

```
User types question ──► Chat Interface
                              │
                              ▼
                   Context Builder ─────────────────┐
                   (assembles portfolio +            │
                    personal + memory context)      │
                              │                     │
                              ▼                     │
                   System Prompt ───────────────────┤
                   (hardcoded rules + injected       │
                    context variables)              │
                              │                     │
                              ▼                     ▼
                         LLM API ◄─── Portfolio Context Payload
                              │         (JSON blob)
                              ▼
                   Response Formatter
                   (enforce WHAT / WHY / ACTION)
                              │
                              ▼
                         User sees response
```

### Key Principle

**The LLM never has to guess.** Every response references the user's actual numbers. If the user asks "Am I diversified?", the LLM doesn't talk about diversification theory — it says _"You have 91% in equities, 45% of that is in one Vanguard global fund, and 63% of your geographic exposure is to the US..."_

---

## 2. The Portfolio Context Payload

This is the **exact JSON blob** injected into every LLM call. It's the difference between Wealthwise and ChatGPT.

### 2.1 Full Schema

```typescript
interface LLMPortfolioContext {
  // ── Personal Context (from user profile) ──
  personal: {
    country: "UK";                        // Always UK — all logic is UK-specific
    age: number;                           // e.g. 38
    risk_tolerance: "low" | "moderate" | "moderate-high" | "high";
    investment_horizon_years: number;      // e.g. 20
    monthly_savings: number;               // GBP
    goal: string;                          // e.g. "long-term wealth accumulation"
    tax_band: "basic" | "higher" | "additional";  // UK tax bands
    pension_contributions_monthly: number;  // GBP
    isa_contributions_monthly: number;      // GBP
    retirement_age_target: number;          // e.g. 60
    employment_status: "employed" | "self-employed" | "business_owner" | "retired";
    dependents: number;                     // 0, 1, 2, etc.
    mortgage_remaining: number | null;      // GBP, null if no mortgage
    annual_income: number | null;           // GBP, approximate
  };

  // ── Portfolio Snapshot (calculated from holdings) ──
  portfolio_snapshot: {
    total_value_gbp: number;               // e.g. 112340.50
    total_cost_gbp: number;                // e.g. 95670.20
    total_gain_gbp: number;                // e.g. 16670.30
    total_gain_pct: number;                // e.g. 17.4
    equity_pct: number;                    // e.g. 82.5
    fixed_income_pct: number;              // e.g. 10.2
    cash_pct: number;                      // e.g. 7.3
    property_pct: number;                  // e.g. 0
    commodity_pct: number;                 // e.g. 0
    multi_asset_pct: number;               // e.g. 0
    unclassified_pct: number;              // e.g. 0
    weighted_ocf: number;                  // Weighted average OCF % (e.g. 0.27)
    num_holdings: number;                  // e.g. 12
    num_accounts: number;                  // e.g. 3
  };

  // ── Accounts Breakdown ──
  accounts: Array<{
    provider: string;                      // e.g. "AJ Bell", "Vanguard"
    account_type: "ISA" | "SIPP" | "GIA" | "LISA" | "Workplace Pension" | "Cash";
    value_gbp: number;
    pct_of_total: number;                  // e.g. 38.2
    holdings: Array<{
      ticker: string | null;              // null for funds without ticker
      name: string;
      type: "ETF" | "Fund" | "Stock" | "Bond";
      asset_class: string;                // equity, fixed_income, cash, property, commodity, multi_asset
      sector: string;                     // global_diversified, tech, healthcare, bonds_global, uk_equity, etc.
      geography: string;                  // global, uk, us, europe, asia, em
      quantity: number;
      cost_basis_pence: number;           // Cost price in pence (GBX)
      current_price_pence: number;        // Current price in pence (GBX)
      value_gbp: number;
      pct_of_portfolio: number;           // % of total portfolio
      gain_gbp: number;
      gain_pct: number;
      ocf_pct: number;
      dividend_yield_pct: number | null;  // Estimated yield
      currency: string;                   // GBP, USD, EUR, etc.
      isin: string | null;               // ISIN identifier
    }>;
  }>;

  // ── Health Scores ──
  health_scores: {
    overall: {
      score: number;                       // 0-10
      grade: "A" | "B" | "C" | "D" | "E";
    };
    dimensions: Array<{
      name: "Risk Alignment" | "Diversification" | "Tax Efficiency" | "Cost Efficiency" | "Cash Management";
      score: number;                       // 0-10
      weight: number;                      // 0.25, 0.25, 0.20, 0.15, 0.15
      detail: string;                      // Brief explanation
    }>;
  };

  // ── Active Insights ──
  insights: Array<{
    severity: "critical" | "warning" | "info";
    type: string;                          // risk_mismatch, fund_overlap, cash_drag, etc.
    title: string;                         // "91% equities — above moderate target"
    detail: string;                        // Longer explanation (2-3 sentences)
    prompt: string;                        // Pre-filled question text for [Ask →]
  }>;

  // ── Tax Summary (calculated from holdings + wrappers) ──
  tax_summary: {
    isa_total_gbp: number;
    isa_allowance_remaining: number;       // £20,000 - contributions so far
    sipp_total_gbp: number;
    sipp_annual_allowance_remaining: number;
    gia_total_gbp: number;
    gia_estimated_cgt_exposure: number;    // Rough unrealised gain in GIA
    gia_dividend_income_estimate: number;  // Estimated dividend income from GIA
    pension_lta_concern: "none" | "approaching" | "exceeded";
  };

  // ── Benchmark Comparison (optional) ──
  benchmark: {
    name: string;                          // e.g. "FTSE All-World", "60/40 Portfolio"
    total_return_pct: number;              // e.g. 12.5
    user_return_pct: number;               // e.g. 14.2
    difference_pct: number;                // e.g. +1.7
    period: string;                        // e.g. "YTD", "1Y", "Since inception"
  } | null;
}
```

### 2.2 What This Enables

| Context Field | Enables The LLM To… |
|---------------|-------------------|
| `personal.age` + `risk_tolerance` | Say "At 38 with moderate risk, 91% equity is aggressive — consider 60-80%" |
| `accounts[].account_type` + `holdings[].asset_class` | Spot tax inefficiency: "Your bonds are in your GIA, move them to your SIPP" |
| `holdings[].ticker` + `holdings[].sector` | Detect overlap: "VWRP and VWRL both track the same index" |
| `health_scores.dimensions[].score` | Prioritise what to fix first: "Your biggest drag is tax efficiency at 4/10" |
| `tax_summary.gia_cgt_exposure` | Advise on CGT harvesting: "You have £12k unrealised gain in your GIA" |
| `portfolio_snapshot.equity_pct` | Run stress tests: "At 91% equity, a 30% crash would lose ~£31k" |
| `benchmark` | Compare: "You're outperforming the FTSE All-World by 1.7% this year" |

### 2.3 Context Builder Implementation

```python
def build_llm_context(user_data, health_scores, insights, selected_account="All"):
    """
    Build the full context payload for LLM injection.
    Called on every chat message.
    """
    personal = user_data["personal_context"]
    accounts = user_data["accounts"]
    
    # Calculate portfolio-level snapshot
    holdings = get_all_holdings(accounts, selected_account)
    snapshot = calculate_snapshot(holdings)
    
    # Build accounts breakdown
    accounts_breakdown = build_accounts_detail(accounts, selected_account)
    
    # Calculate tax summary
    tax_summary = calculate_tax_summary(accounts, personal)
    
    # Benchmark (if history available)
    benchmark = calculate_benchmark(holdings, accounts) if user_data.get("history") else None
    
    return {
        "personal": mask_sensitive(personal),
        "portfolio_snapshot": snapshot,
        "accounts": accounts_breakdown,
        "health_scores": health_scores,
        "insights": insights,
        "tax_summary": tax_summary,
        "benchmark": benchmark,
        "generated_at": datetime.utcnow().isoformat()
    }
```

### 2.4 Token Budget

At the intended scale (~12 holdings, 3 accounts, typical personal context):

| Component | Estimated Tokens |
|-----------|-----------------|
| Personal context | ~150 tokens |
| Portfolio snapshot | ~80 tokens |
| Per account (3) | ~100 each = 300 tokens |
| Health scores | ~100 tokens |
| Insights (3-4) | ~200 tokens |
| Tax summary | ~80 tokens |
| Benchmark | ~50 tokens |
| JSON structure overhead | ~100 tokens |
| **Total per call** | **~1,060 tokens** |

At £9.99/user/month with LLM costs at £1-3/user/month, this is sustainable. Each chat message is:
- **System prompt:** ~1,060 tokens portfolio context + ~500 tokens instructions = ~1,560 tokens
- **User question:** ~50-200 tokens
- **Response:** ~300-600 tokens
- **Total per exchange:** ~2,000-2,400 tokens

---

## 3. System Prompt Architecture

### 3.1 Master System Prompt

```python
SYSTEM_PROMPT_TEMPLATE = """You are Wealthwise, an AI investment co-pilot for UK DIY investors.

You have access to the user's complete portfolio data below. You MUST reference their specific numbers in every response. Never answer generically.

──────────────────────────────────────
PORTFOLIO DATA
──────────────────────────────────────
{portfolio_context_json}

──────────────────────────────────────
HEALTH SCORES
──────────────────────────────────────
{health_scores_text}

──────────────────────────────────────
ACTIVE INSIGHTS
──────────────────────────────────────
{insights_text}

──────────────────────────────────────
BENCHMARK COMPARISON
──────────────────────────────────────
{benchmark_text}

──────────────────────────────────────
RESPONSE FORMAT — Use this structure for every response
──────────────────────────────────────

RESPONSE FORMAT:
1. WHAT — What the answer means in plain English. Reference their numbers.
   Example: "With 91% in equities, your portfolio is significantly exposed to stock market movements..."
   
2. WHY — Why it matters to THIS specific portfolio. Never generic.
   Example: "At age 38 with a moderate risk profile, your equity allocation is 31% above what we'd typically recommend..."

3. ACTION — What they could consider doing. NOT financial advice — always frame as options.
   Example: "Here are a few options worth considering: ..."

If the response is short, merge WHAT and WHY but always include ACTION.

──────────────────────────────────────
HARD RULES
──────────────────────────────────────

1. UK TERMINOLOGY ONLY
   - Use ISA, SIPP, GIA, LISA — NOT 401k, Roth IRA, TFSA
   - Use CGT (Capital Gains Tax), not "capital gains"
   - Use "pension", not "retirement account" (unless comparing)
   - Use £ not $
   - Use "tax year" not "tax season"

2. NO FINANCIAL ADVICE
   - Never say "you should", "I recommend", "the best option is"
   - Always say "you might consider", "one option would be", "some people in your situation..."
   - Never guarantee returns or outcomes
   - Add disclaimer for tax advice: "This isn't tax advice — speak to an accountant"

3. REFERENCE THEIR NUMBERS
   - Every response must include at least ONE specific number from their portfolio
   - If the user asks "Am I diversified?", don't explain diversification theory
   - Say: "Your portfolio has 12 holdings across 3 accounts. 91% is in equities..."

4. BE HONEST ABOUT UNCERTAINTY
   - If unsure about a UK tax rule: "I'm not 100% sure on this — a UK tax adviser could confirm"
   - If the data might be incomplete: "Based on the portfolio you've uploaded..."
   - Never hallucinate regulation

5. KEEP RESPONSES CONCISE
   - Default: under 300 words
   - If user asks for detail: "Here's the short version... [and] Want the full breakdown?"
   - Use bullet points for multiple points, not paragraphs

6. KNOW YOUR LIMITS
   - You only know what's in the portfolio they uploaded
   - If they ask about a holding not in their data: "I can only see what you've uploaded"
   - You cannot execute trades, access brokers, or see real-time prices
   - You can analyse based on the data they provided

──────────────────────────────────────
PERSONAL CONTEXT
──────────────────────────────────────
Age: {age}
Risk tolerance: {risk_tolerance}
Investment horizon: {horizon_years} years
Tax band: {tax_band}
Employment: {employment_status}
Dependents: {dependents}
Monthly savings: £{monthly_savings}
Goal: {goal}
Retirement target age: {retirement_age_target}
"""
```

### 3.2 Variable Injection

```python
def build_system_prompt(context: LLMPortfolioContext) -> str:
    """Build the final system prompt with all variables injected."""
    
    return SYSTEM_PROMPT_TEMPLATE.format(
        portfolio_context_json=json.dumps(context["portfolio"], indent=2),
        health_scores_text=format_health_scores(context["health_scores"]),
        insights_text=format_insights(context["insights"]),
        benchmark_text=format_benchmark(context["benchmark"]),
        # Personal context variables
        age=context["personal"]["age"],
        risk_tolerance=context["personal"]["risk_tolerance"],
        horizon_years=context["personal"]["investment_horizon_years"],
        tax_band=context["personal"]["tax_band"],
        employment_status=context["personal"]["employment_status"],
        dependents=context["personal"]["dependents"],
        monthly_savings=context["personal"]["monthly_savings"],
        goal=context["personal"]["goal"],
        retirement_age_target=context["personal"]["retirement_age_target"],
    )
```

---

## 4. Analysis Capabilities — What the LLM Does

The LLM performs these analyses, conditioned *entirely* on the portfolio context injected. No external tooling needed for the core features (except historical price lookups for stress testing).

### 4.1 Risk Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Am I too risky?" | Equity% vs age-based target. At 38 moderate → 60-80% equity. | `personal.age`, `personal.risk_tolerance`, `portfolio_snapshot.equity_pct` |
| "What if markets crash 30%?" | Portfolio impact = equity_value × 0.3 + fixed_income_value × 0.05 | `portfolio_snapshot.equity_pct`, `holdings[].asset_class`, `holdings[].value_gbp` |
| "Am I concentrated in one stock?" | % of portfolio in top holding | `holdings[].pct_of_portfolio` sorted descending |
| "Is my sector allocation balanced?" | Sector % distribution vs benchmark | `holdings[].sector`, `holdings[].value_gbp` |
| "Am I too international / too UK?" | Geographic % breakdown | `holdings[].geography`, `holdings[].value_gbp` |

### 4.2 Tax Efficiency Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Should I move my bonds?" | Asset class vs wrapper. Bonds in GIA = tax-inefficient. | `accounts[].account_type`, `holdings[].asset_class` |
| "Should I use my ISA allowance?" | Remaining allowance, current cash position | `tax_summary.isa_allowance_remaining`, `portfolio_snapshot.cash_pct` |
| "Am I paying too much CGT?" | Unrealised gains in GIA + dividend income estimate | `tax_summary.gia_estimated_cgt_exposure`, `tax_summary.gia_dividend_income_estimate` |
| "Should I harvest losses?" | Holdings in GIA with negative gain_pct | `holdings[].gain_gbp` (negative values in GIA accounts) |
| "Pension or ISA next?" | Tax band, remaining allowances, age, goal | `personal.tax_band`, `personal.age`, `tax_summary.*` |

### 4.3 Diversification Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Do I have fund overlap?" | Same index tracked by multiple tickers | `holdings[].ticker`, `holdings[].name`, `holdings[].sector` |
| "Am I diversified enough?" | Holdings count, geographic spread, sector spread, asset class mix | `portfolio_snapshot.num_holdings`, all holdings[].geography, .sector, .asset_class |
| "Should I add small cap / EM / property?" | Gaps vs typical allocation for their risk profile | Current allocation vs model portfolio |
| "Am I too heavy in one geography?" | Geographic % breakdown | `holdings[].geography` aggregation |
| "Is my bond allocation right for my age?" | Fixed income % vs age-based rule of thumb | `portfolio_snapshot.fixed_income_pct`, `personal.age` |

### 4.4 Cost Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Am I paying too much?" | Weighted average OCF vs market (typically 0.2-0.5%) | `portfolio_snapshot.weighted_ocf`, `holdings[].ocf_pct` |
| "Should I switch to cheaper funds?" | High-OCF holdings identified | `holdings[].ocf_pct` sorted descending |
| "What are my biggest cost drivers?" | Each holding's cost contribution = value × OCF | `holdings[].ocf_pct` × `holdings[].value_gbp` |
| "Trading fees vs platform fees?" | Not yet — need broker fee data (Tier 2) | Future: `accounts[].platform_fee` |

### 4.5 Cash & Liquidity Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Do I have too much cash?" | Cash% vs optimal 2-5% | `portfolio_snapshot.cash_pct` |
| "Should I deploy my cash?" | Cash value in context of ISA allowance, goals | `holdings[]` where asset_class=cash, `tax_summary.*` |
| "Do I need an emergency fund?" | Total portfolio value, cash position, dependents | `personal.dependents`, cash holdings |

### 4.6 Goal & Planning Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "Am I on track to retire at 60?" | Current portfolio value, savings rate, horizon | `personal.age`, `portfolio_snapshot.total_value_gbp`, `personal.monthly_savings`, `personal.retirement_age_target` |
| "How much should I save each month?" | Gap between current savings and target | Based on goal target (future: Monte Carlo) |
| "Should I overpay mortgage or invest?" | Mortgage remaining, portfolio value, tax band | `personal.mortgage_remaining`, `personal.tax_band` |
| "Am I contributing enough to pension?" | Pension total vs age-based benchmark | SIPP + workplace pension values, `personal.age` |

### 4.7 Benchmark & Performance Analysis

| Question | What LLM Analyses | Context It Uses |
|----------|------------------|-----------------|
| "How am I doing vs the market?" | User return vs benchmark return | `benchmark` object |
| "Is my portfolio beating inflation?" | Portfolio return vs inflation rate | `benchmark.user_return_pct` |
| "Which holdings are dragging?" | Holdings sorted by gain_pct ascending | `holdings[].gain_pct` |

---

## 5. Response Format Enforcement

### 5.1 Post-Processing

After the LLM returns a response, we run a lightweight validator:

```python
def validate_response(response: str, context: LLMPortfolioContext) -> tuple[bool, str]:
    """
    Validate that the LLM response:
    1. Contains at least one number from the user's portfolio
    2. Doesn't contain prohibited phrases (regulated advice)
    3. Follows WHAT/WHY/ACTION structure
    """
    warnings = []
    
    # 1. Check portfolio number reference
    numbers_in_response = extract_numbers(response)
    portfolio_numbers = extract_portfolio_numbers(context)
    
    if not any(num in portfolio_numbers for num in numbers_in_response):
        warnings.append("Response doesn't reference any specific portfolio numbers")
    
    # 2. Check prohibited phrases
    prohibited = [
        "you should", "I recommend", "the best option", 
        "guaranteed", "risk-free", "certain to"
    ]
    for phrase in prohibited:
        if phrase.lower() in response.lower():
            warnings.append(f"Contains potentially regulated advice: '{phrase}'")
    
    # 3. Check structure
    has_what = "WHAT" in response or "what" in response[:200].lower()
    has_action = "ACTION" in response or "consider" in response.lower()
    
    if not (has_what and has_action):
        warnings.append("Response may not follow WHAT/WHY/ACTION structure")
    
    return len(warnings) < 2, "\n".join(warnings)
```

### 5.2 Fallback on Invalid Response

If validation fails significantly, we retry once with a stricter sub-prompt:

> *"Your previous response was too generic or used prohibited language. The user's portfolio total is £X and their equity allocation is Y%. Please re-answer referencing these specific numbers and use the WHAT/WHY/ACTION format."*

---

## 6. Memory — The Core Moat

This is what makes Wealthwise different from ChatGPT. Each session makes the LLM smarter about that specific user.

### 6.1 What We Remember Between Sessions

| What | Stored As | Expiry |
|------|-----------|--------|
| User's personal context (age, risk, goals) | JSON in user profile | Until user updates |
| Holding snapshots (historical) | Array of `{date, portfolio_value, equity_pct}` | Forever (used for trend analysis) |
| Previous questions asked | Array of `{date, question}` | Last 30 days |
| Previous insights shown | Array of `{date, insight_type, dismissed}` | Last 90 days |
| User's preferences ("I don't care about cash drag") | Key-value in user profile | Until changed |
| Risk tolerance history | Array of `{date, stated_risk, inferred_risk}` | Last 12 months |

### 6.2 Memory Injection into System Prompt

```python
def build_memory_context(user_data) -> str:
    """Build the memory section injected into the LLM prompt."""
    
    memory = user_data.get("memory", {})
    previous_questions = memory.get("previous_questions", [])
    previous_insights = memory.get("dismissed_insights", [])
    holding_history = memory.get("holding_snapshots", [])
    
    memory_text = f"""
──────────────────────────────────────
SESSION MEMORY
──────────────────────────────────────
Previous questions you've asked (last 5):
{chr(10).join(f"- {q}" for q in previous_questions[-5:])}

Insights you've dismissed before:
{chr(10).join(f"- {i}" for i in previous_insights) if previous_insights else "- None"}

Portfolio value trend:
{format_value_trend(holding_history)}
"""
    return memory_text
```

### 6.3 Compound Learning

Session 1:
> User: "Am I diversified?"
> LLM: "You have 12 holdings across 3 accounts. Your equity allocation is 91%..."

Session 5 (after user reduced equities):
> User: "Am I diversified?"
> LLM: "Since last month, you reduced equities from 91% to 78%. That's progress toward your moderate target of 60-80%. You still have VWRP and VWRL tracking the same index — want to consolidate those?"

The LLM *remembers* the trend because we inject the holding history.

Session 10:
> User: "What's changed?"
> LLM: "Since you started using Wealthwise 3 months ago: your portfolio is up 4.2%, you've reduced equity exposure from 91% to 72%, and you consolidated two overlapping funds saving 0.15% in OCF..."

---

## 7. Session Memory Schema

```json
{
  "user_memory": {
    "first_seen": "2026-05-15T10:00:00Z",
    "last_active": "2026-06-04T22:00:00Z",
    "session_count": 12,
    "holding_snapshots": [
      {
        "date": "2026-05-15",
        "total_value": 112340,
        "equity_pct": 91,
        "fixed_income_pct": 5,
        "cash_pct": 4,
        "num_holdings": 12
      },
      {
        "date": "2026-06-04",
        "total_value": 118200,
        "equity_pct": 78,
        "fixed_income_pct": 15,
        "cash_pct": 7,
        "num_holdings": 10
      }
    ],
    "previous_questions": [
      "Am I diversified?",
      "What if markets crash 30%?",
      "Should I consolidate VWRP and VWRL?",
      "How much risk am I taking?",
      "Am I on track for retirement at 60?"
    ],
    "dismissed_insights": [
      "cash_drag"
    ],
    "preferences": {
      "show_benchmark": true,
      "risk_review_frequency": "quarterly",
      "preferred_timeframe": "1Y"
    }
  }
}
```

---

## 8. Guardrails & Constraints

### 8.1 Hard Blockers

```python
# These trigger an immediate refusal + redirect
HARD_BLOCKERS = [
    "execute", "trade", "place order", "buy shares", "sell shares",
    "give me financial advice", "what should I do", "tell me exactly what to do",
    "password", "login", "credentials",
    "illegal", "tax evasion", "hide money",
]

# Response when triggered
REFUSAL_TEMPLATE = """
I can't {request_type}, but I can help you think through the options.

Here's what I can tell you based on your portfolio:
- [Option A]: {option_a_detail}
- [Option B]: {option_b_detail}

These are things to discuss with your broker or financial adviser before making any decisions.
"""
```

### 8.2 Soft Boundary Responses

For grey areas (like mortgage vs invest, pension lump sum vs drawdown):

```python
GREY_AREA_TEMPLATE = """
This depends on your personal circumstances, but here's how your portfolio numbers look:

{portfolio_context}

Things to consider:
1. {consideration_1}
2. {consideration_2}
3. {consideration_3}

🤷 I can lay out the trade-offs, but this is one where a financial adviser would be helpful.
"""
```

### 8.3 UK-Specific Validation

The LLM must not reference:
- 401k, Roth IRA, TFSA → Must use ISA, SIPP, GIA, LISA
- W-2, 1099 → Must use P60, P11D, P800
- IRS → Must use HMRC
- Social Security → Must use State Pension
- Medicare → Must use NHS (not relevant but guard against confusion)

We inject a reference table:

```python
UK_US_TERMS_MAP = """
UK TERM : US EQUIVALENT
─────────────────────────────
ISA     : Roth IRA / TFSA
SIPP    : 401k / IRA
GIA     : Taxable brokerage account
LISA    : Not directly equivalent (closest: Roth IRA with home-buying)
CGT     : Capital gains tax
HMRC    : IRS
State Pension : Social Security
P60     : W-2 (but not identical)
NI      : Social Security tax
SDRT    : No US equivalent
"""
```

---

## 9. Prompt Templates per Scenario

### 9.1 First Interaction (New User)

```python
FIRST_INTERACTION = """
{{system_prompt}}

The user has just uploaded their portfolio for the first time.

Start your response with a brief summary:
"Welcome to Wealthwise. Here's what I can see about your portfolio..."

Then immediately highlight:
1. Portfolio total value
2. Overall health grade
3. The MOST important insight (highest severity)
4. A natural follow-up question to engage

Example opener:
"Welcome to Wealthwise 👋

Here's what I can see about your portfolio:
• Total value: £112,340 across 3 accounts
• Health grade: C (6.8/10)

🔴 The biggest thing to address: 91% equities is above what we'd typically recommend for your age and risk profile.

Want me to explain what happens to your portfolio if markets drop 30%?"
"""
```

### 9.2 "Ask →" Button Response

When the user taps [Ask →] on an insight:

```python
ASK_BUTTON_RESPONSE = """
{{system_prompt}}

The user tapped [Ask →] on this insight:
Insight: {insight_title}
Pre-filled question: {insight_prompt}

{{memory_context}}

Respond directly to the question. Use their specific numbers. End by asking:
"Would you like me to go deeper on this, or explore another area of your portfolio?"
"""
```

### 9.3 Follow-Up (Existing User)

```python
FOLLOW_UP = """
{{system_prompt}}

{{memory_context}}

The user has asked questions before. Reference their previous context where relevant.

Respond to: {user_message}

If the question relates to a previous topic they explored, acknowledge it:
"Last time we looked at your equity allocation. Since then..."
"""
```

### 9.4 Stress Testing Scenario

```python
STRESS_TEST = """
{{system_prompt}}

The user wants to understand what would happen to their portfolio in a market crash.

Run this rough simulation:
- Severe crash: Equities -30%, Fixed Income -5%
- Moderate crash: Equities -15%, Fixed Income -2%

Calculate:
- Portfolio value before crash: £{total_value}
- After severe crash: £{total_value - equity_value*0.3 - fi_value*0.05}
- After moderate crash: £{total_value - equity_value*0.15 - fi_value*0.02}

IMPORTANT: This is a rough simulation based on historical patterns. It's not a prediction. Frame as "historically, a crash of this magnitude would have meant..."

Use the user's ACTUAL equity and fixed income values, not generic percentages.
"""
```

### 9.5 Tax Efficiency Deep-Dive

```python
TAX_EFFICIENCY = """
{{system_prompt}}

The user wants to understand their tax efficiency.

You have their tax summary:
- ISA total: £{isa_total} / £20,000 used
- SIPP total: £{sipp_total}
- GIA total: £{gia_total}
- Estimated GIA unrealised gain: £{gia_gain}
- Estimated GIA dividend income: £{gia_dividends}

{{tax_band_context}}

Analyse:
1. Are the most tax-efficient wrappers being used optimally?
2. Is there ISA allowance remaining they should use?
3. Would contributing more to pension reduce their tax bill?
4. Are they at risk of exceeding CGT allowance on GIA gains?
5. Any LISA eligible but not used?

Always caveat: "This isn't tax advice — a qualified accountant can confirm the exact figures for your situation."
"""
```

---

## 10. Cost & Token Budget

### 10.1 Per-Interaction Cost

| Component | Input Tokens | Output Tokens | Total |
|-----------|-------------|---------------|-------|
| System prompt (static) | ~500 | — | 500 |
| Portfolio context (JSON) | ~1,100 | — | 1,100 |
| Memory context | ~200 | — | 200 |
| User message | ~100 | — | 100 |
| Response | — | ~400 | 400 |
| **Per exchange** | **~1,900** | **~400** | **2,300** |

### 10.2 Monthly Cost Estimates

| Usage Pattern | Messages/Month | Tokens/Month | Cost (DeepSeek) | Cost (GPT-4o mini) |
|--------------|---------------|--------------|-----------------|-------------------|
| Light user | 30 | 69k | ~£0.07 | ~£0.17 |
| Average user | 100 | 230k | ~£0.23 | ~£0.58 |
| Power user | 300 | 690k | ~£0.69 | ~£1.73 |
| Heavy user | 1,000 | 2.3M | ~£2.30 | ~£5.75 |

At £9.99/mo pricing, even heavy users are profitable with DeepSeek.

### 10.3 Token Saving Strategies

| Technique | Tokens Saved | Implementation |
|-----------|-------------|----------------|
| Compress JSON (remove nulls, use short keys) | ~200/call | Strip nulls, use `a` for asset_class, `g` for geography in payload |
| Cache unchanged context | ~1,100/message after 1st | Only re-send context if portfolio changed |
| Truncate memory to last 5 questions | ~100/call | Don't send all 30 days of history |
| Compress insight text | ~100/call | Use 1-line summaries, full detail only on [Ask →] |

---

## 11. Testing & Quality Framework

### 11.1 Test Scenarios

```python
TEST_SCENARIOS = [
    {
        "name": "risk_question",
        "context": high_equity_young_user,
        "user_message": "Am I taking too much risk?",
        "expected": "References 91% equity, age 38, moderate risk target 60-80%"
    },
    {
        "name": "overlap_detection",
        "context": dual_global_fund_user,
        "user_message": "Do I have duplicate funds?",
        "expected": "Identifies VWRP and VWRL tracking same index"
    },
    {
        "name": "tax_efficiency",
        "context": bonds_in_gia_user,
        "user_message": "Can I be more tax efficient?",
        "expected": "Flags bonds in GIA, suggests move to SIPP"
    },
    {
        "name": "cash_drag",
        "context": high_cash_user,
        "user_message": "What should I do with my cash?",
        "expected": "15% cash identified, suggests deploying to ISA"
    },
    {
        "name": "crash_scenario",
        "context": retirement_approaching_user,
        "user_message": "What if markets crash?",
        "expected": "Simulates -30% equity, -5% bonds, shows £ impact"
    },
    {
        "name": "prohibited_advice_edge_case",
        "context": normal_user,
        "user_message": "Just tell me what to do with my money",
        "expected": "Refuses to give regulated advice, offers analysis instead"
    },
    {
        "name": "generic_question",
        "context": normal_user,
        "user_message": "What are the best ETFs?",
        "expected": "Says they can only analyse based on uploaded data, asks what goals"
    },
    {
        "name": "uk_vs_us_terminology",
        "context": normal_user,
        "user_message": "How's my 401k doing?",
        "expected": "Corrects to SIPP/pension, uses UK terms"
    },
]
```

### 11.2 Quality Metrics

| Metric | Target | How We Measure |
|--------|--------|---------------|
| Portfolio number reference rate | >90% of responses | Extract numbers from response, check overlap with portfolio values |
| Hallucination rate (UK tax rules) | <2% | Manual audit of 100 random responses |
| Response structure compliance | >80% | Check for WHAT/WHY/ACTION or reasonable equivalent |
| User re-engagement rate | >30% click [Ask →] | Track button clicks after initial insight |
| Session length retention | >3 messages/session | Count messages per session |
| User satisfaction (implicit) | <5% "this is generic" feedback | Scan for negative feedback phrases |

### 11.3 Automated Test Pipeline

```bash
#!/bin/bash
# Run weekly — tests LLM quality against known scenarios

# Test each scenario
for scenario in "${TEST_SCENARIOS[@]}"; do
    python test_llm_response.py \
        --scenario "$scenario" \
        --model "deepseek/deepseek-v4-flash" \
        --output "test_results/$(date +%Y-%m-%d)/$scenario.json"
done

# Generate report
python generate_qa_report.py \
    --results_dir "test_results/$(date +%Y-%m-%d)" \
    --output "test_results/$(date +%Y-%m-%d)/report.md"
```

---

## 12. Future: Multi-User & Shared Portfolios

### 12.1 Couples / Joint View

```python
JOINT_CONTEXT = """
You are analysing a JOINT portfolio for {user_a_name} and {user_b_name}.

Individual details:
- {user_a_name}: Age {a_age}, {a_risk_tolerance}, {a_tax_band}
- {user_b_name}: Age {b_age}, {b_risk_tolerance}, {b_tax_band}

Combined portfolio: £{combined_value}

Account ownership:
{ownership_breakdown}

When giving advice, specify whose allowance, whose CGT liability, etc.
For example: "This GIA is in {user_a_name}'s name, so the CGT gain of £X uses their allowance..."
"""
```

### 12.2 Multiple Portfolios

```python
MULTI_CONTEXT = """
You have access to {n} portfolios for this user:
{portfolio_list}

The user may switch between portfolios. Check which one is active: {active_portfolio_name}

When comparing, use language like: "Your SIPP is performing better than your ISA this year..."
"""
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│              WEALTHWISE LLM ENGINE              │
├─────────────────────────────────────────────────┤
│                                                 │
│  DATA WE FEED THE LLM (every message):          │
│  ┌───────────────────────────────────────────┐  │
│  │ ✅ Personal context (age, risk, tax band) │  │
│  │ ✅ Portfolio snapshot (totals, splits)     │  │
│  │ ✅ Per-account holdings (ticker, value, %) │  │
│  │ ✅ Health scores (5 dimensions)            │  │
│  │ ✅ Active insights (2-4)                  │  │
│  │ ✅ Tax summary (ISA/SIPP/GIA positions)   │  │
│  │ ✅ Benchmark comparison                    │  │
│  │ ✅ Session memory (past Qs, trends)        │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ANALYSIS IT CAN DO:                            │
│  ┌───────────────────────────────────────────┐  │
│  │ 🔴 Risk Analysis                           │  │
│  │ 🟡 Tax Efficiency                          │  │
│  │ 🟢 Diversification (overlap, spreads)      │  │
│  │ 💰 Cost Analysis                           │  │
│  │ 💵 Cash & Liquidity                        │  │
│  │ 🎯 Goal & Retirement Planning              │  │
│  │ 📊 Benchmark Comparison                    │  │
│  │ 📉 Stress Testing (crash sims)            │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  RULES: UK only, reference numbers, no advice   │
│  RESPONSE: WHAT → WHY → ACTION                 │
│  MEMORY: Gets smarter every session (THE MOAT)  │
│                                                 │
└─────────────────────────────────────────────────┘
```
