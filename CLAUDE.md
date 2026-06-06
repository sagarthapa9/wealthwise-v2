# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project overview

WealthWise v2 is a rewrite of the original Streamlit app into a modern full-stack application. It provides UK-focused AI-powered investment analysis with portfolio data ingestion, persistent storage, and an interactive dashboard.

**Stack:** FastAPI (Python) + PostgreSQL + React/Vite + Docker Compose + uv

**Key docs (read these for full context):**
- `docs/chatbot-migration-analysis.md` — Why context-injection over ReAct loop, context data gap analysis, architecture evolution plan
- `docs/agentic-ai-architecture.md` — ReAct pattern, memory augmentation (working/episodic/semantic), production-grade patterns
- `docs/deployment-guide.md` — VPS + Cloud Run deploy, CI/CD pipeline, monitoring

## Essential commands

```bash
# Start the full stack
docker compose up --build

# Backend only (from backend/)
uv run uvicorn app.main:app --reload

# Frontend only (from frontend/)
npm run dev

# Install backend dependencies
cd backend && uv sync

# Install frontend dependencies
cd frontend && npm install

# Run database migrations (Phase 2+)
cd backend && uv run alembic upgrade head
```

## Project structure

```
wealthwise-v2/
├── docker-compose.yml
├── .env
├── docs/                    # architecture, deployment, migration analysis
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/          # health, ticker, portfolio, profile, accounts, allocations, router
│   │   ├── models/          # holding, profile, account (SQLAlchemy ORM)
│   │   ├── schemas/         # holding, profile, account (Pydantic v2)
│   │   ├── services/        # portfolio_data, portfolio_calc, health_score, insight_engine,
│   │   │                    # prompt_builder, hook_templates, export_report,
│   │   │                    # classification, ticker_provider (new in Phase 3)
│   │   ├── db/database.py   # async engine + session
│   │   └── core/config.py   # pydantic-settings
│   └── alembic/
├── frontend/
│   ├── vite.config.js       # proxy /api → backend:8000
│   └── src/
│       ├── App.jsx
│       ├── App.css
│       └── components/      # TickerSearch, PortfolioTable, AllocationSection,
│                             # AllocationDonut, AllocationTable, HookInsightCard,
│                             # ProfilePanel, SettingsModal
```

## Architecture decisions

- **Backend:** FastAPI with async endpoints, SQLAlchemy 2.0 async ORM, Pydantic v2 schemas
- **Database:** PostgreSQL 17 with asyncpg driver
- **Frontend:** Vanilla React (no router needed yet), plain CSS, fetches via proxy
- **Infrastructure:** Docker Compose for local dev, Vite proxy for API calls
  - File watching uses polling (`CHOKIDAR_USEPOLLING=1`) for Docker volume hot reload
  - Frontend hits `/api/v1/health` (not `/api/health`)
- **Python management:** uv (not pip/venv) for dependency management
- **The user is new to React** — explain hooks, JSX, props clearly
- **Ticker data provider abstraction** — `TickerProvider` ABC in `services/ticker_provider.py`, with `YFinanceProvider` as the current implementation. Switching providers = new class + config change. The endpoint never imports yfinance directly.
- **Holding classification stored at creation** — `type`, `asset_class`, `sector`, `geography`, `currency`, `ocf_pct`, `dividend_yield_pct`, `isin` are auto-populated from ticker lookup and stored in the DB. The old `_infer_*()` heuristics in `allocations.py` have been deleted.

## UI Design System — All new UI must follow this

The app uses a **monochrome Financial Freedom Tracker** style defined in
`specs/portfolio_search.md`. Every new component must follow:

### Visual theme
- **Colour:** Monochrome — black (`#1a1a1a`), white (`#fff`), greys (`#d4d4d4`, `#e0e0e0`, `#f5f5f5`)
- **No colour accents** — no blues, reds, or greens in the UI chrome (gain/loss numbers use `#059669` green and `#dc2626` red)
- **Background:** `#f5f5f5` page, `#fff` card with subtle shadow
- **Typography:** Sans-serif, clean weights. Ticker symbols in monospace
- **Corners:** `border-radius: 10px-16px` on cards and major elements, `6px` on badges
- **Spacing:** Generous padding throughout (`1.5rem-2rem`)

### Interaction patterns
- **Ticker entry:** Always-visible search input → autocomplete dropdown (ETF badge + name + exchange) → "+" button
- **Portfolio table:** Read-only display with delete (🗑️) actions — no inline editing
- **Action bar at bottom:** Import CSV | Currency selector | Analyze Portfolio button
- **Summary strip:** Below the card, shows totals in a horizontal strip

### Reference
- Design spec: `C:\SourceCode\wealthwise\specs\portfolio_search.md`
- CSS file: `frontend/src/App.css`

## Migration from original project (C:\SourceCode\wealthwise)

The original Streamlit app at `C:\SourceCode\wealthwise\` has business logic we
reuse. Here's what moves where:

### Copy as-is (pure Python — no Streamlit dependency)
Place these into `backend/app/services/`:
- `lib/health_score.py` — 5-dimension portfolio health scoring
- `lib/insight_engine.py` — Portfolio insight detectors (concentration, drift, etc.)
- `lib/portfolio_calc.py` — Allocation calculations (asset class, sector, geo)
- `lib/portfolio_data.py` — Reference for DB schema design (Holding, Account models)
- `lib/prompt_builder.py` — Insight-to-AI-prompt converter
- `lib/hook_templates.py` — Tab-specific insight card templates
- `lib/export_report.py` — PDF report generation (fpdf2)

### Rewrite as React components (were Streamlit UI)
- `allocation_chart.py` → React chart (Recharts in Phase 3)
- `allocation_table.py` → React table component
- `insight_card.py` / `insights_section.py` → React insight cards
- `portfolio_sidebar.py` → React sidebar
- `ai_chat_bar.py` → React chat input + message display
- `export_button.py` → React download button

### Rewrite as FastAPI endpoints (were CLI/Streamlit-bound)
- `chatBot_dpsk.py` → FastAPI endpoint + DeepSeek API call
- `memory_manager.py` → PostgreSQL conversation storage
- `prompt_manager.py` → Backend config service
- `functions/fundAnalysis.py` → API tool endpoints (yfinance)

## Current build status

- Phase 1 (Scaffolding): ✅ Complete — FastAPI + React + Docker Compose working
- Phase 2a (Manual Portfolio Builder): ✅ Complete — holdings CRUD, ticker search, summary
- Phase 2b (Profile + Accounts): ✅ Complete — profile CRUD, accounts CRUD, inline editing, settings modal
- Phase 2c (Allocations + Health + Insights): 🔄 Partial — backend services migrated and allocations UI works, but:
  - ❌ Health score API + UI missing (no endpoint or component)
  - ❌ Insights list API + UI missing (7 detectors exist, no endpoint or component)
  - ❌ "Ask AI" button rendered but inert (deferred to Phase 3b)
  - ❌ PDF export button missing (export_report.py migrated but not wired)
- Phase 3 (LLM Analysis Engine): 📅 In Progress
  - ✅ Prerequisite (Holding Data Enrichment) — `classification.py`, `ticker_provider.py` created, holding model + schemas extended with 8 new fields, ticker endpoint returns classification data, purchase price input added to fix cost basis bug, `_infer_*()` deleted from allocations.py, alembic migration created
  - ✅ Phase 0 (Chat Models) — ChatSession, ChatMessage, UserMemory models + MemoryService + migration
  - ✅ Phase 1 (Context Builder) — `context_builder.py` assembles full LLMPortfolioContext payload from DB
  - ✅ Phase 2 (Chat Service) — `chat_service.py` + `system_prompt.py` + `guardrails.py`
  - ✅ Phase 3 (API Endpoint) — `POST /api/v1/chat` + `GET /api/v1/chat/{session_id}/messages`
  - ✅ Phase 4 (Frontend) — ChatPanel.jsx with loading/empty/error/message/reasoning states, HookInsightCard "Ask AI" wired, ChatPanel integrated into App.jsx, CSS styles added
  - ⬜ Phase 5+: ReAct loop, episodic/semantic memory (deferred)

### Current API endpoints
- `GET /api/health` — health check
- `GET /api/v1/health` — v1 health check (DB ping)
- `GET /api/v1/ticker/{symbol}` — ticker lookup (via abstract TickerProvider, includes classification fields)
- `POST /api/v1/portfolio/holdings` — create holding
- `GET /api/v1/portfolio/holdings` — list holdings
- `PUT /api/v1/portfolio/holdings/{id}` — update holding
- `DELETE /api/v1/portfolio/holdings/{id}` — delete holding
- `GET /api/v1/portfolio/summary` — portfolio totals
- `GET /api/v1/profile` — get profile (auto-creates defaults)
- `PUT /api/v1/profile` — create/update profile
- `GET /api/v1/accounts` — list accounts
- `POST /api/v1/accounts` — create account
- `PUT /api/v1/accounts/{id}` — update account
- `DELETE /api/v1/accounts/{id}` — delete account
- `GET /api/v1/portfolio/allocations?tab=` — asset/sector/geo breakdowns + insight hook
- `POST /api/v1/chat` — Send message + get LLM portfolio analysis (context-injected)
- `GET /api/v1/chat/{session_id}/messages` — Load conversation history

## Memory Management Rules — Always Follow

### At the START of every session:
1. Read CLAUDE.md and PHASE_LOG.md silently
2. Give me a 3-bullet summary of where we are
3. Ask what to work on before doing anything

### During the session — update files when:
- A phase or task is marked complete
- A new decision is made (library choice, pattern, naming)
- A bug is found and fixed (log the cause and fix)
- I confirm something is working
- My understanding of a concept improves

### At the END of every session (or when I say "wrap up"):
1. Update PHASE_LOG.md with:
   - What was completed today ✅
   - What is in progress 🔄
   - What is blocked and why ❌
   - Next steps for next session
2. Update CLAUDE.md if any of these changed:
   - Tech decisions
   - Folder structure
   - My skill level notes
   - Project description
3. Confirm what was saved before ending

### Rules for updating files:
- Never delete previous phase logs — append only
- Keep CLAUDE.md under 150 lines (summarise if growing)
- Be specific — "POST /api/v1/portfolio/upload working" not "did some API work"
- If unsure whether to log something — log it
