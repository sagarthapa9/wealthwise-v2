# Wealthwise — Portfolio-Aware Buy Zone Feature Spec

**Status:** Draft for review
**Date:** 7 June 2026
**Author:** Huerixa

---

## 1. Overview

A feature that analyses each holding in the user's portfolio and surfaces personalised buying opportunities — not based on generic market signals, but on what makes sense **for that specific user's portfolio, cost basis, allocation, and goals.**

**Core principle:** "Should YOU buy more of this, given what you already own?"

---

## 2. Why Generic Buy Zones Fail

| Generic tool | What it tells you |
|---|---|
| Motley Fool | "Buy! This stock is undervalued" |
| TradingView | "RSI < 30 — oversold" |
| Simply Wall St | "Fair value upside: 22%" |
| ChatGPT | "Based on RSI and MA, it's a buy" |

**What they ALL miss:**
- You already own it (maybe too much)
- Your cost basis (are you averaging down or catching a falling knife?)
- Your current allocation (are you already overweight?)
- Your portfolio overlap (do you own 3 funds that all track the S&P 500?)
- Your risk profile (are you a 60/40 investor looking at a high-volatility stock?)

**Wealthwise's advantage:** Only Wealthwise knows all of the above. That's the moat.

---

## 3. Signal Types

### 3.1 Price vs Cost Basis Signal
**Logic:**
- Current price < your average cost → you're underwater → potential averaging-down opportunity
- Current price >> your average cost → you're up → consider taking profits instead

**Scoring:**
| Condition | Signal |
|---|---|
| Price < avg cost by >10% | Strong averaging-down potential |
| Price < avg cost by 3-10% | Moderate averaging-down |
| Price near avg cost (±3%) | Neutral — no cost basis edge |
| Price > avg cost by 10-20% | Consider taking partial profits |
| Price > avg cost by >20% | Strong profit-taking signal |

### 3.2 Price vs Fair Value Signal
**Source:** Free daily data via yfinance + external fair value estimates
- P/E ratio vs sector average
- P/B ratio vs historical range
- Dividend yield vs 5-year average
- Analyst consensus target price (if available)

**Output:**
- "Trading at 15% discount to sector average P/E"
- "Dividend yield at 4.8% — in top quartile of its 5-year range"

### 3.3 Technical Entry Signal
**Source:** Free daily OHLCV data (yfinance / Alpha Vantage)

| Indicator | What it tells | Data needed |
|---|---|---|
| RSI (14) | Oversold (<30) or overbought (>70) | 14 daily closes |
| Price vs 50-day SMA | Short-term trend | 50 daily closes |
| Price vs 200-day SMA | Long-term trend | 200 daily closes |
| MACD crossover | Momentum shift | 26 daily closes |

**Combined scoring:**
- ✅ RSI < 35 (oversold)
- ✅ Price below 200-day SMA (on sale from long-term trend)
- ✅ MACD showing bullish crossover or divergence
→ All 3 = strong technical buy zone

### 3.4 Allocation Context Signal
**This is the Wealthwise moat.**

| User's current allocation | What this means for buying |
|---|---|
| Holding is UNDER target allocation by >5% | ✅ Buy signal — you're underweight, price aside |
| Holding is AT target allocation (±5%) | 🟡 Cautious — any buy increases overweight risk |
| Holding is OVER target allocation by >5% | ❌ Don't buy — you're already overweight |
| No target set | Default to equal-weight or market-cap proxy |

### 3.5 Overlap & Concentration Signal
**Checks before recommending:**
- Does this holding overlap with other funds you already own?
- Would adding more concentrate an already-concentrated sector?
- Are you buying more of a single stock when you already own it inside an index fund?

**Output:**
- ❌ "Adding more VUAG increases your S&P 500 exposure to 78% of equities. You already hold it in VWRP, HSBC American Index, and L&G US Index. Skip."
- ✅ "This ETF has minimal overlap with your existing holdings. Adding would improve diversification."

### 3.6 Tax Wrapper Context Signal
**UK-specific — another Wealthwise moat.**

| Wrapper | Signal |
|---|---|
| You maxed your ISA allowance? | Alert if new buy would spill into GIA |
| Buying in GIA when ISA allowance remains? | "You have £8k ISA allowance left — buy here instead to avoid CGT" |
| SIPP purchase with limited pension allowance? | Flag if approaching annual allowance |

---

## 4. Combined Buy Zone Score

Aggregate all signals into a single **0–100 Buy Zone Score** per holding, weighted by what matters most for the user.

### Default Weighting
| Signal category | Weight |
|---|---|
| Cost basis (price vs your avg cost) | 30% |
| Allocation context (under/over target) | 25% |
| Technical entry (RSI, MA, MACD) | 20% |
| Fair value (P/E, dividend yield) | 15% |
| Overlap/concentration risk | 10% |

### Buy Zone Bands
| Score | Label | Action |
|---|---|---|
| 75–100 | 🟢 Strong Buy | "Good time to add. Price is down, you're underweight, no overlap concerns." |
| 50–74 | 🟡 Weak Buy | "Price is attractive but check allocation first." |
| 25–49 | 🟠 Hold | "No strong signal either way. Keep current position." |
| 0–24 | 🔴 Avoid | "Don't add. Overvalued, overweight, or both." |

---

## 5. UX Design

### 5.1 Portfolio View — Buy Zone Badges
Each holding row gets a small coloured badge:

```
| Holding        | Value     | Allocation | Buy Zone |
|----------------|-----------|------------|----------|
| VWRP           | £34,200   | 34%        | 🟢 72    |
| HSBC American  | £18,500   | 18%        | 🟡 54    |
| Apple          | £12,300   | 12%        | 🔴 18    |
| UK Gilts ETF   | £8,100    | 8%         | 🟢 81    |
```

### 5.2 Insights Section — Buying Opportunities Card
Dedicated insight card generated after each portfolio refresh:

> **📈 Buying Opportunities (2 found)**
>
> **VWRP — Strong Buy (72/100)**
> Price is down 8% from your average cost of £95. You're underweight by 6%. RSI at 32 (oversold). Good DCA opportunity.
>
> **UK Gilts ETF — Strong Buy (81/100)**
> Yields at 4.8% — 5-year high. Your allocation is only 8% vs 15% target. No overlap concerns.
>
> **[Ask →] "How much should I add to VWRP?"**

### 5.3 Per-Holding Detail View
When user taps a holding:

```
VWRP — Vanguard FTSE All-World UCITS ETF

Current price: £87.20
Your avg cost: £95.30 (-8.5%)

📊 Buy Zone Score: 72/100 — Strong Buy

✅ Below your cost basis by 8.5% — averaging-down opportunity
✅ Price below 200-day SMA by 6% — on sale vs long-term trend
✅ RSI: 32 — oversold territory
✅ Allocation: 34% vs 40% target — 6% underweight
✅ No overlap detected with other holdings

⚠️ Sector exposure is 58% US — adding more increases US concentration
```

### 5.4 Composite Buy Zone — "Top-up suggestion"
Aggregate view showing best buying opportunity across entire portfolio:

> **💰 Best Top-up Opportunity**
> Add £2,000 to VWRP → brings allocation to 36% (still under 40% target)
> Cost basis improves from £95.30 to £94.70
> No CGT impact (held in ISA)
>
> **[One-tap → Add to wishlist]**

---

## 6. Data Requirements

### 6.1 Data Sources
| Data | Source | Cost |
|---|---|---|
| Daily OHLCV prices | yfinance (free) | £0 |
| P/E, P/B, dividend yield | yfinance or Alpha Vantage | £0–£20/mo |
| Analyst targets | Financial Modeling Prep (paid) | £20–£50/mo |
| FX rates (for multi-currency) | Free FX API | £0 |

### 6.2 Data Already Available (from CSV import)
- Holdings (ticker, quantity, cost basis, wrapper)
- Portfolio allocation across all accounts
- Transaction history (for cost basis tracking)

### 6.3 New Data to Store
- Daily price cache for each ticker (last 200 days)
- Fair value indicators (updated weekly)
- Target allocation (user-set or auto-derived)

---

## 7. Implementation Plan

### Phase 1 — Basic (2-3 days dev)
- [ ] Price vs cost basis comparison on all holdings
- [ ] Simple allocation context (under/over default targets)
- [ ] RSI calculation from daily price data
- [ ] Badge display on portfolio view

### Phase 2 — Enhanced (3-5 days dev)
- [ ] Fair value indicators (P/E, dividend yield vs sector)
- [ ] Moving average comparisons (50-day, 200-day)
- [ ] MACD signal
- [ ] Buying Opportunities insight card
- [ ] Combined Buy Zone Score calculation

### Phase 3 — Contextual (3-5 days dev)
- [ ] Overlap detection between holdings
- [ ] Tax wrapper awareness (ISA/GIA/SIPP context)
- [ ] Target allocation integration
- [ ] Per-holding detail view with full breakdown
- [ ] Top-up suggestion aggregator

---

## 8. Edge Cases & Risks

| Edge case | Handling |
|---|---|
| **User has no cost basis data** (e.g., CSV without prices) | Default to price-only signals; score caps at 60 |
| **ETF/Fund doesn't have P/E data** | Weight shifted to technical + allocation signals |
| **User hasn't set target allocation** | Default to market-cap weighted benchmark (e.g., global market cap) |
| **Ticker not found on yfinance** | Fallback to manual price entry or skip signal |
| **Price data < 200 days** | Use whatever is available and adjust confidence weighting |
| **Multi-currency holdings** | Convert to user's base currency using daily FX rate |
| **New holding with zero cost basis** | Treat as "just bought" — no averaging-down yet |

---

## 9. Key Differentiators vs Competitors

| Competitor | What they do | What Wealthwise does better |
|---|---|---|
| **TradingView** | Technical analysis on any ticker | Adds YOUR cost basis and portfolio context |
| **Simply Wall St** | Fair value analysis per stock | Cross-references with your actual allocation |
| **Sharesight** | Portfolio tracking, CGT reports | No buy signals; no AI context |
| **Motley Fool** | Stock picks and fair value | Doesn't know what you already own |
| **ChatGPT** | Can recommend buy if you paste portfolio | No memory, no persistence, hallucinates UK tax |

**Wealthwise's unique data advantage:**
- Your cost basis across all accounts (not just one broker)
- Your real-time portfolio allocation
- Your target allocation (learned over time)
- Your transaction history (for DCA analysis)
- Full tax wrapper context

---

## 10. Open Questions for Sagar

1. **Target allocation:** Should users set their own? Auto-detect from portfolio history? Or both?
2. **Price data frequency:** Daily update on app open? Or user-triggered refresh?
3. **Buy Zone vs Sell Zone:** Should we flag overvalued holdings for selling too, or keep it buy-only for MVP?
4. **Free vs paid:** Is Buy Zone a free feature or subscription gated?

---

## Appendix: Quick Cost Estimate

| Item | Monthly cost |
|---|---|
| yfinance API | £0 |
| Alpha Vantage (premium for UK data) | £0–£20 |
| Financial Modeling Prep (optional) | £20–£50 |
| **Total per month** | **£0–£70** |
| **Cost per user** (assuming 1000 users) | **£0–£0.07/user/mo** |

Data costs are negligible. The moat is in the portfolio-aware logic, not the data.
