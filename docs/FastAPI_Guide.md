# WealthWise FastAPI Backend Developer Guide

> **Stack:** Python · FastAPI · PostgreSQL · SQLAlchemy · Alembic
>
> A beginner-friendly reference covering BaseSettings, database configuration, SQLAlchemy models, and Alembic migrations with Vue/Angular comparisons.

---

## Table of Contents

1. [__init__.py — What It Is and Why It Matters](#1-initpy--what-it-is-and-why-it-matters)
2. [BaseSettings and Configuration](#2-basesettings-and-configuration)
3. [Database Setup — database.py](#3-database-setup--databasepy)
4. [Holdings Model — SQLAlchemy](#4-holdings-model--sqlalchemy)
5. [Alembic Migrations](#5-alembic-migrations)
6. [APIRouter — Modular Route Organisation](#6-apirouter--modular-route-organisation)

---

## 1. `__init__.py` — What It Is and Why It Matters

`__init__.py` is a special Python file that tells Python a folder is a **package** — meaning other files can import from it. Without it, Python treats the folder as just a folder, not a module.

### The Core Problem It Solves

**Without `__init__.py`:**

```
app/
  models/
    holding.py

from app.models import Holding
# ModuleNotFoundError
```

**With `__init__.py`:**

```
app/
  models/
    __init__.py      <- marks as package
    holding.py

from app.models import Holding
# Works perfectly
```

### Vue/Angular Comparison

```javascript
// JavaScript — every file importable automatically
import { Holding } from "./models/holding"
```

```python
# Python WITHOUT __init__.py
from app.models import Holding  # ModuleNotFoundError

# Python WITH __init__.py
from app.models import Holding  # Works perfectly
```

### Two Ways to Use `__init__.py`

#### 1. Empty File — Just Makes Folder Importable

```python
# app/models/__init__.py
# (completely empty — this is fine and common)
```

This is the minimum requirement. Just its presence marks the folder as a Python package. You will see empty `__init__.py` files everywhere in FastAPI projects.

#### 2. Re-export Imports — Cleaner Import Paths

```python
# app/models/__init__.py  — with re-exports
from app.models.holding import Holding
from app.models.user import User
from app.models.transaction import Transaction
```

Now your imports across the whole project become much shorter:

```python
# Without re-exports — long and verbose
from app.models.holding import Holding
from app.models.user import User

# With re-exports in __init__.py — clean
from app.models import Holding, User, Transaction
```

### WealthWise Project — Every Folder Needs One

```
app/
├── __init__.py              <- makes app a package
├── main.py
├── api/
│   ├── __init__.py          <- makes api a package
│   └── v1/
│       ├── __init__.py      <- makes v1 a package
│       ├── health.py
│       ├── ticker.py
│       └── portfolio.py
├── models/
│   ├── __init__.py          <- makes models a package
│   └── holding.py
├── schemas/
│   ├── __init__.py
│   └── holding.py
├── db/
│   ├── __init__.py
│   └── database.py
└── core/
    ├── __init__.py
    └── config.py
```

### Recommended Contents for WealthWise

| File | Contents | Why |
|------|----------|-----|
| `app/__init__.py` | Empty | Just marks `app` as a package |
| `app/models/__init__.py` | `from app.models.holding import Holding` | Clean imports for Alembic and routes |
| `app/schemas/__init__.py` | `from app.schemas.holding import HoldingCreate, HoldingRead` | Clean imports in route files |
| `app/api/v1/__init__.py` | Empty | `routers.py` handles registration |
| `app/db/__init__.py` | Empty | `database.py` imported directly |
| `app/core/__init__.py` | Empty | `config.py` imported directly |

### Why Your Alembic Import Works

```python
# In alembic/env.py
from app.models import Holding  # noqa: F401

# This works because:
#   app/__init__.py        exists → app is a package
#   app/models/__init__.py exists → app.models is a package
#   app/models/holding.py  exists → Holding class is found

# Remove any __init__.py and you get:
# ModuleNotFoundError: No module named "app.models"
```

### Common Mistake and Fix

```python
# Error you will see without __init__.py:
ModuleNotFoundError: No module named "app.models"
ModuleNotFoundError: No module named "app.schemas"
ImportError: cannot import name "Holding" from "app.models"

# Fix — check every folder in the import path:
# [ ] app/__init__.py          exists?
# [ ] app/models/__init__.py   exists?
# [ ] Holding class imported inside it (if using re-exports)?
```

> **Tip:** Think of `__init__.py` like `index.js` in a JavaScript module — it marks the entry point of a folder and optionally re-exports things for cleaner imports throughout your project.

---

## 2. BaseSettings and Configuration

`BaseSettings` is a special class from the `pydantic-settings` library that combines two powerful features: **Pydantic type validation** and **automatic environment variable reading** from `.env` files or system environment.

### The Problem It Solves

**Without BaseSettings** — fragile, manual config management:

```python
import os
database_url = os.getenv("DATABASE_URL")           # could be None!
debug = os.getenv("DEBUG", "false") == "true"       # manual conversion
app_name = os.getenv("APP_NAME", "WealthWise API")  # repeated everywhere
```

**With BaseSettings** — clean and automatic:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "WealthWise API"
    database_url: str = "postgresql+asyncpg://wealthwise:wealthwise@db:5432/wealthwise"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

### Priority Order — Where Settings Come From

Priority (highest to lowest):

1. **System environment variables** — terminal or Docker
2. **`.env` file values** — your local `.env` file
3. **Default values in the class** — fallback

### What Each Line Does

| Line | What it does |
|------|-------------|
| `app_name: str = "WealthWise API"` | String validated; default used if `APP_NAME` not set |
| `database_url: str = "postgresql+asyncpg://..."` | Override in `.env` for different environments |
| `debug: bool = False` | Auto-converts `true/false/1/0` from `.env` to Python bool |
| `model_config = {...}` | Tells BaseSettings to read from the `.env` file |

### `.env` File Setup

```bash
# .env  <- NEVER commit this to Git
APP_NAME=WealthWise API
DATABASE_URL=postgresql+asyncpg://wealthwise:wealthwise@db:5432/wealthwise
DEBUG=true
```

```bash
# .env.example  <- SAFE to commit, no real values
APP_NAME=your-app-name
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DEBUG=false
```

```bash
# Add to .gitignore immediately
echo ".env" >> .gitignore
```

### Using Settings Across Your App

```python
# In any file — single import, access everything
from app.core.config import settings

print(settings.database_url)
print(settings.debug)
print(settings.app_name)
```

### Vue/Angular Comparison

| Concept | Vue/Angular | FastAPI BaseSettings |
|---------|-------------|---------------------|
| Environment config | `.env` + `process.env.VUE_APP_X` | `.env` + `settings.x` |
| Type safety | Manual or TypeScript | Automatic via Pydantic |
| Default values | `process.env.X \|\| "default"` | `x: str = "default"` |
| Bool conversion | Manual | Automatic |
| Global access | Vuex store / Angular service | `from config import settings` |

> **Tip:** `settings = Settings()` creates one singleton instance loaded once at app startup — like a global config service in Angular, no registration needed.

---

## 3. Database Setup — `database.py`

This file sets up everything needed to connect to PostgreSQL and manage database sessions throughout the app.

```
Your FastAPI app
      |
  engine              ← manages connections to PostgreSQL
      |
  AsyncSessionLocal   ← factory that creates database sessions
      |
  get_db()            ← hands a fresh session to each API request
      |
  Base                ← blueprint all your models inherit from
```

### The Engine

```python
engine = create_async_engine(
    settings.database_url,
    echo=False,    # Set True to see SQL queries in logs
    pool_size=5,   # Keep 5 connections open and reused
)
```

| Parameter | What it does |
|-----------|-------------|
| `settings.database_url` | PostgreSQL connection string from your `.env` |
| `echo=False` | Set `True` in dev to see every SQL query in terminal |
| `pool_size=5` | Keeps 5 connections open — much faster than opening new ones each request |

### Why Async?

```python
# Synchronous — blocks everything
result = session.execute(query)        # app freezes waiting

# Asynchronous — non-blocking
result = await session.execute(query)  # handles other requests while waiting
```

### Connection Pool Visualised

```
Without pool:
Request 1 → open connection → query → close → 100ms
Request 2 → open connection → query → close → 100ms

With pool_size=5:
Request 1 → grab from pool → query → return to pool → 10ms
Request 2 → grab from pool → query → return to pool → 10ms
           ^ connection already open — much faster
```

### `expire_on_commit=False`

```python
# expire_on_commit=True (default) — causes errors
holding = Holding(name="VOOG", shares=100)
await session.commit()
print(holding.name)  # ERROR — object expired after commit!

# expire_on_commit=False — works as expected
holding = Holding(name="VOOG", shares=100)
await session.commit()
print(holding.name)  # "VOOG" — still accessible
```

### The `get_db()` Dependency

FastAPI automatically runs this before and after every route that needs a database session:

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session           # hands session to your route
        finally:
            await session.close()   # always cleans up
```

**Request timeline:**

1. Request hits `GET /api/v1/holdings`
2. FastAPI sees `Depends(get_db)`
3. `get_db()` creates fresh session
4. `yield session` → route runs its queries
5. Route returns response to client
6. `finally: session.close()` always runs (even on error)

### How You Use `get_db` in a Route

```python
@router.get("/holdings")
async def list_holdings(
    db: AsyncSession = Depends(get_db)  # FastAPI injects the session
):
    result = await db.execute(select(Holding))
    return result.scalars().all()
```

### Vue/Angular Comparison

| `database.py` concept | Vue/Angular equivalent |
|------------------------|----------------------|
| `create_async_engine` | Axios base instance with base URL configured |
| `pool_size=5` | HTTP keep-alive connection reuse |
| `AsyncSessionLocal` | Axios instance factory |
| `get_db()` dependency | Angular service injected into a component |
| `yield session` | `ngOnInit` + `ngOnDestroy` lifecycle hooks |
| `Base` | TypeScript abstract base class |

---

## 4. Holdings Model — SQLAlchemy

The `Holding` class maps directly to a PostgreSQL table. Each instance of the class = one row in the database.

### Full Model Code

```python
class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cost_basis_per_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Holding(id={self.id}, ticker={self.ticker}, qty={self.quantity})>"
```

### The `Mapped` Type Annotation Pattern

```python
id: Mapped[int] = mapped_column(Integer, primary_key=True)
#   |       |       |
#   |  Python type  Database column definition
#   SQLAlchemy hint for IDE autocomplete

# TypeScript equivalent:
interface Holding {
  ticker: string;    // ← same as Mapped[str]
  quantity: number;  // ← same as Mapped[float]
}
```

### Column Reference

| Column | Type | Required | Default | Purpose |
|--------|------|----------|---------|---------|
| `id` | Integer | Auto | Auto-increment | Unique row identifier |
| `ticker` | String(10) | Yes | None | Stock symbol e.g. VWRL |
| `name` | String(200) | Yes | None | Full fund name |
| `quantity` | Float | Yes | 1.0 | Shares owned (fractional ok) |
| `cost_basis_per_share` | Float | Yes | 0.0 | Price paid per share |
| `current_price` | Float | Yes | 0.0 | Live price from yfinance |
| `created_at` | DateTime(tz) | Auto | now() | Row creation time |
| `updated_at` | DateTime(tz) | Auto | now() | Auto-updates on change |

### `nullable=False` — Database-Level Validation

```python
# Even if Python forgets to check, PostgreSQL rejects it
holding = Holding(name="Vanguard", quantity=10)
# ticker is missing → PostgreSQL throws error immediately
```

### Timestamps Comparison

| Column | Set on INSERT | Set on UPDATE | Who sets it |
|--------|---------------|---------------|-------------|
| `created_at` | Yes — once, never changes | Never touched again | PostgreSQL |
| `updated_at` | Yes — same as created_at | Every time row changes | PostgreSQL |

### What This Becomes in PostgreSQL

```sql
CREATE TABLE holdings (
    id                   SERIAL PRIMARY KEY,
    ticker               VARCHAR(10)  NOT NULL,
    name                 VARCHAR(200) NOT NULL,
    quantity             FLOAT        NOT NULL DEFAULT 1.0,
    cost_basis_per_share FLOAT        NOT NULL DEFAULT 0.0,
    current_price        FLOAT        NOT NULL DEFAULT 0.0,
    created_at           TIMESTAMPTZ  DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  DEFAULT NOW()
);
```

### Calculated Fields You Can Add Later

```python
total_cost    = quantity x cost_basis_per_share
current_value = quantity x current_price
profit_loss   = current_value - total_cost
gain_percent  = (profit_loss / total_cost) x 100
```

> **Tip:** Consider adding `currency: Mapped[str] = mapped_column(String(3), default="GBP")` — your UI already has a currency selector and this future-proofs multi-currency portfolios.

---

## 5. Alembic Migrations

Alembic is **version control for your database** — exactly like Git is version control for your code. You change your Python model, Alembic generates the SQL automatically.

| Git (code) | Alembic (database) |
|------------|-------------------|
| Tracks changes to Python files | Tracks changes to database tables |
| `commit` history | migration history |
| `git revert` | `alembic downgrade` |
| `git apply` | `alembic upgrade head` |

### Does Alembic Create the Database?

| Question | Answer |
|----------|--------|
| Creates tables if they do not exist? | **YES** |
| Creates columns based on models? | **YES** |
| Works on a completely empty database? | **YES** |
| Creates the PostgreSQL database itself? | **NO** — Docker does this |

### The Critical Import in `env.py`

```python
from app.db.database import Base
from app.models import Holding  # noqa: F401

# Why import Holding if not used directly?
#   Importing registers it with Base.metadata automatically
#   Base.metadata is the map of ALL your tables
#   Alembic reads this map to know what tables exist

# Add EVERY new model here:
from app.models import Holding      # noqa: F401
from app.models import User         # noqa: F401
from app.models import Transaction  # noqa: F401
```

### Step-by-Step Migration Process

**Step 1 — Start Docker**

```bash
docker-compose up -d db
# Creates empty PostgreSQL wealthwise database
# No tables yet
```

**Step 2 — Generate Migration File**

```bash
alembic revision --autogenerate -m "create holdings table"
```

Compares your models to the empty database and generates:

```python
# alembic/versions/abc123_create_holdings_table.py

def upgrade() -> None:
    op.create_table("holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        ...
    )

def downgrade() -> None:
    op.drop_table("holdings")  # ← undo the migration
```

**Step 3 — Apply the Migration**

```bash
alembic upgrade head
# head = apply ALL pending migrations up to latest
# Before: empty PostgreSQL database
# After:  holdings table with all columns created
```

**Step 4 — Verify It Worked**

```bash
docker exec -it wealthwise_db psql -U wealthwise -d wealthwise

# Then list tables:
# Schema |      Name       | Type
# -------+-----------------+------
# public | holdings        | table
# public | alembic_version | table  ← tracks migration history
```

### Daily Commands Reference

| Command | What it does |
|---------|-------------|
| `alembic revision --autogenerate -m "desc"` | Create migration after changing a model |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back one migration |
| `alembic downgrade base` | Roll back ALL — empty database |
| `alembic history` | See full migration history |
| `alembic current` | See current applied version |
| `alembic upgrade head --sql` | Offline: generate SQL without connecting |

### Typical WealthWise Workflow

```bash
# Add currency column to Holding model, then:
alembic revision --autogenerate -m "add currency to holdings"
# Generates: ALTER TABLE holdings ADD COLUMN currency VARCHAR(3)

alembic upgrade head
# Runs it on PostgreSQL

# Changed your mind?
alembic downgrade -1
# Runs DROP COLUMN currency — rolls back cleanly
```

### Three Things to Always Remember

1. **Alembic does NOT create the PostgreSQL database** — Docker does that; Alembic only creates tables
2. **Always review generated migration files** before running `upgrade head` — autogenerate is good but not always perfect
3. **Import every new model in `env.py`** — or Alembic cannot detect it exists

---

## 6. APIRouter — Modular Route Organisation

`APIRouter` is a FastAPI class that acts as a mini-app within your app. It lets you group related routes in separate files and plug them all into the main app cleanly — keeping your codebase modular and maintainable.

### The Problem It Solves

**Without APIRouter** — everything in one file (messy):

```python
# main.py
@app.get("/health")
@app.get("/ticker/search")
@app.post("/ticker/add")
@app.get("/portfolio")
@app.post("/portfolio/analyze")
@app.delete("/portfolio/{id}")
# ... 100s of routes all in one file
```

**With APIRouter** — clean and modular:

```
health.py    → handles /health routes
ticker.py    → handles /ticker routes
portfolio.py → handles /portfolio routes
routers.py   → plugs them all together
main.py      → clean entry point
```

### Your `routers.py` File

```python
from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.ticker import router as ticker_router
from app.api.v1.portfolio import router as portfolio_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(ticker_router)
api_v1_router.include_router(portfolio_router)
```

### Your `health.py` — Tag Defined on the Router

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])  # ← tag set here, not at registration


@router.get("/health")
async def health():
    return {"status": "OK"}
```

Defining the tag on the router itself is cleaner than setting it at registration time — the router owns its own identity and does not rely on whoever registers it to remember to add the tag.

### Two Ways to Add Tags — Comparison

| Approach | Where tag is set | Recommended? |
|----------|-----------------|-------------|
| Your way (health.py) | `router = APIRouter(tags=["health"])` | **Yes** — router owns its tag |
| Alternative (routers.py) | `include_router(health_router, tags=["health"])` | Works but less clean |

### How It Connects to `main.py`

```python
# main.py
from fastapi import FastAPI
from app.api.routers import api_v1_router

app = FastAPI()

app.include_router(
    api_v1_router,
    prefix="/api/v1"    # ← all routes get this prefix
)
```

### How Routes Get Their Full Paths

| File | Decorator | Full URL |
|------|-----------|----------|
| `health.py` | `@router.get("/health")` | `GET /api/v1/health` |
| `ticker.py` | `@router.get("/search")` | `GET /api/v1/ticker/search` |
| `ticker.py` | `@router.post("/add")` | `POST /api/v1/ticker/add` |
| `portfolio.py` | `@router.get("/holdings")` | `GET /api/v1/portfolio/holdings` |
| `portfolio.py` | `@router.post("/holdings")` | `POST /api/v1/portfolio/holdings` |
| `portfolio.py` | `@router.delete("/holdings/{id}")` | `DELETE /api/v1/portfolio/holdings/{id}` |

### The Full WealthWise Route Tree

```
main.py
  └── app.include_router(api_v1_router, prefix="/api/v1")
           │
      routers.py (api_v1_router)
           │
           ├── health_router
           │     GET  /api/v1/health
           │
           ├── ticker_router
           │     GET  /api/v1/ticker/search
           │     POST /api/v1/ticker/add
           │
           └── portfolio_router
                 GET    /api/v1/portfolio/holdings
                 POST   /api/v1/portfolio/holdings
                 PUT    /api/v1/portfolio/holdings/{id}
                 DELETE /api/v1/portfolio/holdings/{id}
                 POST   /api/v1/portfolio/analyze
```

### Why `v1` in the Name?

```python
# API versioning — release breaking changes without
# breaking existing clients
/api/v1/health      ← current version (clients use this)
/api/v2/health      ← future version with breaking changes
                       old clients still use v1 unaffected
```

### What Swagger UI Shows at `/docs`

```
Swagger UI (http://localhost:8000/docs)

  ── health ──
     GET  /api/v1/health

  ── ticker ──
     GET  /api/v1/ticker/search
     POST /api/v1/ticker/add

  ── portfolio ──
     GET    /api/v1/portfolio/holdings
     POST   /api/v1/portfolio/holdings
     DELETE /api/v1/portfolio/holdings/{id}
```

### Vue/Angular Comparison

| Concept | Vue/Angular | FastAPI APIRouter |
|---------|-------------|-------------------|
| Grouping routes | Vue Router routes array per module | APIRouter per feature file |
| Registering routes | `router.addRoute()` or `RouterModule` | `app.include_router()` |
| Route prefixes | `children: []` with path prefix | `prefix="/portfolio"` |
| API versioning | Route guard or middleware | `prefix="/api/v1"` |
| Auto docs | No built-in equivalent | Swagger UI at `/docs` auto-generated |

### Health Endpoint — Why It Exists

| Use Case | How it helps |
|----------|-------------|
| Docker health check | Docker pings `/health` to confirm container is ready |
| Load balancer | AWS/nginx checks `/health` before routing traffic |
| React frontend | App checks `/health` on startup to confirm API is up |
| Debugging | First thing to test when something breaks |
| CI/CD pipeline | Deployment scripts wait for `/health` 200 before proceeding |

### Enhanced Health Check — Also Pings the Database

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))  # ping the database
        db_status = "OK"
    except Exception:
        db_status = "ERROR"

    return {
        "status": "OK",
        "database": db_status    # confirms API + DB both up
    }
```

### Three Key Benefits of APIRouter

1. **Separation of concerns** — each feature lives in its own file; `health.py` only knows about health routes, `portfolio.py` only knows about portfolio routes
2. **Team-friendly** — multiple developers work on different routers simultaneously without conflicts
3. **Reusable** — a router can be included in multiple apps; swap out a router without touching anything else

---

> **WealthWise FastAPI Developer Guide — End of Document**
>
> Built incrementally, one phase at a time.
