# WealthWise v2 — Phase Log

## Phase 1: Project Scaffolding ✅

**Completed:** 29 May 2026

### What was built
- ✅ FastAPI backend project with uv (pyproject.toml, deps installed)
- ✅ API health check endpoint (`GET /api/health` and `GET /api/v1/health`)
- ✅ React + Vite frontend project with dev server config
- ✅ Frontend fetches and displays API health status
- ✅ Docker Compose with 3 services (api, db, frontend)
- ✅ Backend Dockerfile with uv multi-stage build
- ✅ Frontend Dockerfile with Node 24
- ✅ PostgreSQL 17 with health check and persistent volume
- ✅ Vite proxy config for `/api` -> backend
- ✅ Project-wide .env file
- ✅ CLAUDE.md and PHASE_LOG.md for memory continuity
- ✅ Business logic copied from original project to `backend/app/services/`
- ✅ All service imports verified working
- ✅ Docker tested by user — file watching added for hot reload in containers
- ✅ Frontend personalised with user name and hit `/api/v1/health` directly

### Key decisions made
- Stack: FastAPI + PostgreSQL + React/Vite + Docker Compose + uv
- Vanilla React (no router, no CSS framework for now)
- Python 3.14, Node 24, PostgreSQL 17
- uv for Python package management
- Reusable business logic copied as-is into `app/services/` with updated imports
- Vite dev server uses polling (CHOKIDAR_USEPOLLING) for Docker volume hot reload
- Frontend uses `/api/v1/health` path (not `/api/health`)

### Next up
- Phase 2: CSV/PDF Parser — data model + file upload + parsing engine

---

## Session 2 — 31 May 2026

### Completed ✅
- Database layer: async SQLAlchemy engine, session, Base
- Holding ORM model (id, ticker, name, quantity, cost_basis_per_share, current_price, timestamps)
- Pydantic schemas: HoldingCreate, HoldingUpdate, HoldingResponse, PortfolioSummary
- Alembic initialized with async support, first migration created
- 6 API endpoints: ticker lookup, CRUD holdings, portfolio summary
- yfinance added to dependencies
- React portfolio builder UI: PortfolioTable, TickerRow, PortfolioSummary
- TickerRow auto-fetches name + price from backend on ticker blur
- All frontend builds cleanly (vite build successful)

### Files created (Phase 2)
- `backend/app/db/database.py` — async engine + session dependency
- `backend/app/models/holding.py` — Holding ORM model
- `backend/app/schemas/holding.py` — request/response schemas
- `backend/app/api/v1/ticker.py` — GET /ticker/{symbol}
- `backend/app/api/v1/portfolio.py` — CRUD + summary
- `backend/alembic/env.py` — async alembic config
- `backend/alembic/versions/f87dd7bb818c_create_holdings_table.py` — initial migration
- `frontend/src/components/TickerRow.jsx` — editable row
- `frontend/src/components/PortfolioTable.jsx` — table container
- `frontend/src/components/PortfolioSummary.jsx` — totals card
- `frontend/src/App.jsx` — replaced with portfolio builder layout
- `frontend/src/App.css` — table and card styles

### In progress 🔄
- Need to run `docker compose up --build` to test end-to-end (DB, API, frontend all together)
- Alembic migration needs to be applied via `docker compose exec api uv run alembic upgrade head`

### Next session checklist
1. `docker compose up --build`
2. `docker compose exec api uv run alembic upgrade head`
3. Test: `curl http://localhost:8000/api/v1/ticker/VWRL`
4. Open http://localhost:5173 — add holdings, verify auto-lookup, save, refresh
5. Phase 2 is complete — decide what's next
