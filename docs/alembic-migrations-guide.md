# Alembic Migrations Guide

Alembic is the database migration tool for SQLAlchemy. It lets you **evolve your database schema** over time as your models change — without losing data.

---

## Quick Start — Order of Operations

When setting up the stack from scratch:

```bash
# 1. Start all services (PostgreSQL + API + frontend)
docker compose up --build

# 2. In a separate terminal, run ALL pending migrations
docker compose exec api uv run alembic upgrade head

# 3. Verify
docker compose exec api uv run alembic current
```

The API container connects to PostgreSQL via Docker networking — no host-side client needed.

---

## The Big Picture

There are **two separate commands** — don't confuse them:

| Step | Command | What it does |
|------|---------|--------------|
| **1. Generate** | `alembic revision --autogenerate -m "message"` | **Creates** a migration `.py` file by comparing your SQLAlchemy models against the current database |
| **2. Apply** | `alembic upgrade head` | **Runs** the migration against the database (creates/alters tables) |

You can commit the generated `.py` file to git — your teammates apply it with step 2.

---

## Real Example: Adding Profile & Account Tables

Here's exactly what happened when we added the `Profile` and `Account` models to this project.

### 1. We wrote the models

**`backend/app/models/profile.py`** — defines a `profiles` table:
```python
class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    risk_tolerance: Mapped[str] = mapped_column(String(20), nullable=False, default="moderate")
    # ... more columns
```

**`backend/app/models/account.py`** — defines an `accounts` table:
```python
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="Manual Entry")
    account_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # ... more columns
```

We also added `account_id` to the existing `Holding` model.

### 2. We registered the models

Alembic's `env.py` needs to **import your models** so it knows they exist:

```python
# backend/alembic/env.py
from app.db.database import Base
from app.models import Holding           # registers Holding with Base
from app.models import ChatSession, ChatMessage, UserMemory  # noqa: F401
```

When we added `Profile` and `Account`, we imported them in `__init__.py`:

```python
# backend/app/models/__init__.py
from app.models.holding import Holding
from app.models.profile import Profile
from app.models.account import Account
from app.models.chat import ChatSession, ChatMessage, UserMemory

__all__ = ["Holding", "Profile", "Account", "ChatSession", "ChatMessage", "UserMemory"]
```

Since `env.py` already does `from app.models import Holding`, and `__init__.py` imports everything in `__all__`, the new models are automatically registered with `Base.metadata`. For autogenerate to detect new models, they must be:
1. Imported in `app/models/__init__.py` (so the import chain reaches them)
2. Listed in `alembic/env.py` (which imports from `app.models`)
3. Inheriting from `app.db.database.Base`
4. Have `__tablename__` set

### 3. We generated the migration

```bash
alembic revision --autogenerate -m "add profile and accounts tables"
```

This created: `backend/alembic/versions/5d39d57103a8_add_profile_and_accounts_tables.py`

Alembic compared `Base.metadata` (all our models) against the actual PostgreSQL schema and detected:
- `profiles` table — **not in DB yet →** generates `CREATE TABLE`
- `accounts` table — **not in DB yet →** generates `CREATE TABLE`
- `holdings.account_id` column — **not in DB yet →** generates `ALTER TABLE ADD COLUMN`

The generated file looks like this:

```python
"""add profile and accounts tables
Revision ID: 5d39d57103a8
Revises: f87dd7bb818c        # ← links to the previous migration
"""

def upgrade() -> None:
    op.create_table("profiles", ...)
    op.create_table("accounts", ...)
    op.add_column("holdings", sa.Column("account_id", ...))

def downgrade() -> None:
    op.drop_column("holdings", "account_id")
    op.drop_table("accounts")
    op.drop_table("profiles")
```

**Always review the generated file** before applying it — autogenerate isn't perfect and might miss things like index renames that look like drop+create.

### 4. We applied the migration

```bash
alembic upgrade head
```

This runs all pending migrations (in order) against the database. After this, the `profiles`, `accounts`, and updated `holdings` tables exist in PostgreSQL.

### 5. We committed everything to git

The migration `.py` file goes in version control so everyone on the team gets the same schema.

---

## Migration Chain

Migrations form a chain. Each migration has:
- Its own `revision` ID (e.g. `5d39d57103a8`)
- A `down_revision` pointing to the previous migration (e.g. `f87dd7bb818c`)

Current chain (all 4 migrations):

```
f87dd7bb818c (create holdings table)
      ↓
5d39d57103a8 (add profile and accounts tables)
      ↓
e2c9b4f7a1d3 (add holding classification fields — type, asset_class, sector, etc.)
      ↓
a1b2c3d4e5f6 (create chat tables — chat_sessions, chat_messages, user_memory)
```

Alembic tracks which have been applied in the `alembic_version` table:

```
alembic_version
┌──────────────────────────────┐
│ version_num                  │
├──────────────────────────────┤
│ a1b2c3d4e5f6                 │ ← latest applied (head)
└──────────────────────────────┘
```

---

## Commands Cheat Sheet

```bash
# Create a migration (autodetect changes from your models)
alembic revision --autogenerate -m "description of change"

# See what's pending (dry-run)
alembic upgrade head --sql

# Apply all pending migrations
alembic upgrade head

# Apply +1 (next migration only)
alembic upgrade +1

# Rollback last migration
alembic downgrade -1

# Rollback to a specific migration
alembic downgrade f87dd7bb818c

# View history
alembic history

# View current version
alembic current
```

---

## In Docker

The API container only runs uvicorn — migrations don't run automatically. They must be run manually after the stack starts.

### Order of Operations

```bash
# 1. Start everything (PostgreSQL + API + frontend)
docker compose up --build

# (Wait for both the db and api containers to be healthy)

# 2. In a separate terminal, run migrations
docker compose exec api uv run alembic upgrade head

# 3. Verify
docker compose exec api uv run alembic current
```

### All Commands

```bash
# Apply all pending migrations
docker compose exec api uv run alembic upgrade head

# Create a new autogenerated migration
docker compose exec api uv run alembic revision --autogenerate -m "description"

# Create a manual (empty) migration
docker compose exec api uv run alembic revision -m "description"

# Rollback last migration
docker compose exec api uv run alembic downgrade -1

# Check current version
docker compose exec api uv run alembic current

# View migration history
docker compose exec api uv run alembic history

# See what's pending
docker compose exec api uv run alembic check

# Or go inside the container
docker compose exec api sh
# then: uv run alembic upgrade head
```

### Auto-run migrations on startup (optional)

To run migrations automatically when the container starts, modify `backend/Dockerfile`:

```dockerfile
# Instead of just uvicorn:
CMD alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Common Gotchas

| Problem | Fix |
|---------|-----|
| `Target database is not up to date` | Run `alembic upgrade head` |
| New model not detected by autogenerate | Make sure it's imported in `models/__init__.py` and `env.py` imports it |
| `FAILED: No revision ID in message` | Add `-m "message"` — it's required |
| Wondering what's applied? | Check the `alembic_version` table in PostgreSQL |
