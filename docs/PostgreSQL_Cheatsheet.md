# WealthWise PostgreSQL Cheatsheet
> Local Docker Development Reference

**Connection Details**

| Host | Port | Database | Username | Password |
|------|------|----------|----------|----------|
| localhost | 5432 | wealthwise | wealthwise | wealthwise |

---

## 1. Connecting to the Database

### Method A — From Your Host Machine (requires psql installed)
```bash
psql -h localhost -p 5432 -U wealthwise -d wealthwise
# Password prompt appears — type: wealthwise
```

### Method B — Inside Docker Container (no local psql needed)
```bash
# Step 1 — find container name
docker ps

# Step 2 — enter container (use the name/ID from step 1, not a hardcoded one — they change on every recreate)
docker exec -it <container_name> bash

# Step 3 — connect
psql -U wealthwise -d wealthwise

# One-liner:
docker exec -it <container_name> psql -U wealthwise -d wealthwise
```

### Method C — Connection String (DBeaver / TablePlus / FastAPI)
```
postgresql://wealthwise:wealthwise@localhost:5432/wealthwise

Host: localhost   Port: 5432   DB: wealthwise
User: wealthwise  Pass: wealthwise
```

### Method D — Skip Password Prompt
```bash
# Windows CMD
set PGPASSWORD=wealthwise && psql -h localhost -U wealthwise -d wealthwise

# Windows PowerShell
$env:PGPASSWORD="wealthwise"; psql -h localhost -U wealthwise -d wealthwise

# Mac / Linux
PGPASSWORD=wealthwise psql -h localhost -U wealthwise -d wealthwise
```

> **Tip:** Easiest in dev: Method B — docker exec directly into the container. No local psql installation needed.

---

## 2. psql Meta Commands (inside the psql prompt)

| Command | What it does |
|---------|--------------|
| `\l` | List all databases |
| `\c wealthwise` | Connect to a specific database |
| `\dt` | List all tables in current database |
| `\d holdings` | Describe holdings — columns, types, constraints |
| `\d+ holdings` | Detailed description including indexes and storage |
| `\di` | List all indexes |
| `\dn` | List all schemas |
| `\du` | List all users and roles |
| `\x` | Toggle expanded display (easier for wide rows) |
| `\x auto` | Auto-switch expanded mode based on terminal width |
| `\timing` | Show query execution time after each result |
| `\i /path/to/file.sql` | Run SQL from a file |
| `\o /path/to/out.txt` | Save query output to a file |
| `\e` | Open last query in text editor |
| `\q` | Quit psql |
| `\?` | List all backslash commands |
| `\h SELECT` | SQL syntax help for SELECT |

---

## 3. Docker Commands

| Command | What it does |
|---------|--------------|
| `docker-compose up -d db` | Start only the db container |
| `docker-compose up -d` | Start all containers |
| `docker-compose down` | Stop — data preserved in volume |
| `docker-compose down -v` | Stop AND DELETE all data ⚠️ |
| `docker-compose restart db` | Restart db container |
| `docker-compose logs db` | View PostgreSQL logs |
| `docker-compose logs -f db` | Follow live logs |
| `docker ps` | List running containers |
| `docker exec -it <name> psql -U wealthwise -d wealthwise` | Connect to psql directly |
| `docker exec -it <name> bash` | Open shell inside container |
| `docker-compose exec db pg_dump -U wealthwise wealthwise > backup.sql` | Backup to SQL file |
| `docker-compose exec db psql -U wealthwise wealthwise < backup.sql` | Restore from backup |

> ⚠️ **Warning:** `docker-compose down -v` permanently deletes your pgdata volume and ALL data. Only use to start completely fresh.

---

## 4. SQL Query Cheatsheet — holdings Table

### SELECT — Reading Data

| Description | SQL |
|-------------|-----|
| All rows | `SELECT * FROM holdings;` |
| Specific columns | `SELECT ticker, quantity, current_price FROM holdings;` |
| One row by id | `SELECT * FROM holdings WHERE id = 1;` |
| Find by ticker | `SELECT * FROM holdings WHERE ticker = 'VWRL';` |
| Qty greater than 10 | `SELECT * FROM holdings WHERE quantity > 10;` |
| Sort by price desc | `SELECT * FROM holdings ORDER BY current_price DESC;` |
| Top 5 by total value | `SELECT * FROM holdings ORDER BY current_price * quantity DESC LIMIT 5;` |
| Count all rows | `SELECT COUNT(*) FROM holdings;` |
| Wildcard ticker search | `SELECT * FROM holdings WHERE ticker LIKE 'V%';` |
| Newest first | `SELECT * FROM holdings ORDER BY created_at DESC;` |

### INSERT — Adding Data

```sql
-- Add a new holding
INSERT INTO holdings (ticker, name, quantity, cost_basis_per_share, current_price)
VALUES ('VWRL', 'Vanguard FTSE All-World UCITS ETF', 10.5, 98.50, 102.30);

-- Add and return the new row immediately
INSERT INTO holdings (ticker, name, quantity, cost_basis_per_share, current_price)
VALUES ('VUAG', 'Vanguard S&P 500 UCITS ETF', 5, 78.20, 80.10)
RETURNING *;
```

### UPDATE — Changing Data

```sql
-- Update price for one ticker
UPDATE holdings SET current_price = 105.50 WHERE ticker = 'VWRL';

-- Update multiple columns
UPDATE holdings SET current_price = 105.50, quantity = 12 WHERE id = 1;

-- Update and return changed row
UPDATE holdings SET quantity = 15 WHERE ticker = 'VWRL' RETURNING *;
```

### DELETE — Removing Data

```sql
-- Delete one row
DELETE FROM holdings WHERE id = 1;

-- Delete by ticker
DELETE FROM holdings WHERE ticker = 'VWRL';

-- Delete all rows (keeps table structure)
DELETE FROM holdings;

-- Fast full clear — cannot be rolled back
TRUNCATE TABLE holdings;
```

> ⚠️ **Warning:** Always use `WHERE` with `DELETE` and `UPDATE` or every row is affected. Run a `SELECT` with the same `WHERE` first to confirm.

---

## 5. Portfolio Analysis Queries

```sql
-- Total current portfolio value
SELECT ROUND(SUM(quantity * current_price)::numeric, 2) AS total_value
FROM holdings;

-- Total amount invested
SELECT ROUND(SUM(quantity * cost_basis_per_share)::numeric, 2) AS total_cost
FROM holdings;

-- Profit / loss per holding
SELECT
    ticker,
    ROUND((quantity * current_price)::numeric, 2)                          AS current_value,
    ROUND((quantity * cost_basis_per_share)::numeric, 2)                   AS total_cost,
    ROUND(((current_price - cost_basis_per_share) * quantity)::numeric, 2) AS profit_loss
FROM holdings ORDER BY profit_loss DESC;

-- Percentage gain per holding
SELECT ticker,
    ROUND(((current_price - cost_basis_per_share)
        / NULLIF(cost_basis_per_share, 0) * 100)::numeric, 2) AS gain_pct
FROM holdings ORDER BY gain_pct DESC;

-- Holdings not updated in last hour
SELECT * FROM holdings WHERE updated_at < NOW() - INTERVAL '1 hour';
```

---

## 6. Inspect Tables and Schema

```sql
-- All columns with types
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'holdings' ORDER BY ordinal_position;

-- Indexes on holdings
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'holdings';

-- Table size on disk
SELECT pg_size_pretty(pg_total_relation_size('holdings')) AS size;

-- Check current Alembic migration version
SELECT * FROM alembic_version;

-- All tables with row counts
SELECT relname AS table_name, n_live_tup AS row_count
FROM pg_stat_user_tables ORDER BY n_live_tup DESC;
```

---

## 7. Transactions

```sql
BEGIN;

    UPDATE holdings SET quantity = 20 WHERE ticker = 'VWRL';
    UPDATE holdings SET quantity = 10 WHERE ticker = 'VUAG';

COMMIT;    -- saves both changes atomically

-- Something went wrong? Undo everything:
ROLLBACK;  -- reverts all changes since BEGIN
```

---

## 8. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Connection refused` | Container not running | `docker-compose up -d db` |
| `password authentication failed` | Wrong credentials | Check `.env` or `PGPASSWORD` |
| `database does not exist` | DB not created yet | `docker-compose down -v` then `up` |
| `column does not exist` | Migration not applied | `alembic upgrade head` |
| `relation does not exist` | Table not created | `alembic upgrade head` |
| `null value violates not-null` | Missing required field | Check all required columns |
| `duplicate key value` | Primary key collision | Check before insert |
| `SSL connection error` | Docker does not use SSL | Add `?sslmode=disable` to URL |

---

## 9. Quick Reference Card

| Task | Command |
|------|---------|
| Connect via Docker | `docker exec -it <name> psql -U wealthwise -d wealthwise` |
| List all tables | `\dt` |
| Describe a table | `\d holdings` |
| Toggle readable display | `\x auto` |
| See all data | `SELECT * FROM holdings;` |
| Count rows | `SELECT COUNT(*) FROM holdings;` |
| Check Alembic version | `SELECT * FROM alembic_version;` |
| Run pending migrations | `alembic upgrade head` (terminal — not inside psql) |
| Backup database | `docker-compose exec db pg_dump -U wealthwise wealthwise > backup.sql` |
| Wipe and start fresh | `docker-compose down -v` then `docker-compose up -d` |
| Quit psql | `\q` |

---

*WealthWise PostgreSQL Cheatsheet — Local Docker Development Reference*
