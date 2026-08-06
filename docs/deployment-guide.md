# WealthWise v2 — Deployment & CI/CD Guide

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Production Architecture](#2-production-architecture)
3. [Option A — Deploy on a VPS with Docker Compose](#3-option-a--deploy-on-a-vps-with-docker-compose)
4. [Option B — Deploy on Cloud Run + Cloud SQL](#4-option-b--deploy-on-cloud-run--cloud-sql)
5. [Environment Variables](#5-environment-variables)
6. [CI/CD Pipeline with GitHub Actions](#6-cicd-pipeline-with-github-actions)
7. [Monitoring & Maintenance](#7-monitoring--maintenance)
8. [Database Migration & Deployment Best Practices](#8-database-migration--deployment-best-practices)

---

## 1. Prerequisites

### What you need before starting

| Item | Example |
|------|---------|
| A domain name | `wealthwise.example.com` |
| Cloud provider account | Hetzner, DigitalOcean, GCP, AWS, or Azure |
| GitHub repository | Already set up at `github.com/sagarthapa9/wealthwise-v2` |
| Docker installed | For local testing |
| PostgreSQL database | Managed service (Cloud SQL, RDS, etc.) for production |

### Environment checklist

```bash
# Verify locally before deploying
python --version   # 3.14+
node --version     # 24+
docker --version   # 29+
```

---

## 2. Production Architecture

```
                           ┌──────────────┐
                           │  Cloud DNS   │
                           │  yourdomain  │
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │   Caddy      │
                           │  (auto HTTPS)│
                           └──────┬───────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                   │
        ┌──────▼──────┐   ┌──────▼──────┐    ┌───────▼──────┐
        │  Frontend   │   │  FastAPI    │    │  PostgreSQL  │
        │  (React SPA │   │  API server │    │  (managed)   │
        │   served by │   │  2-4 replicas│   │  e.g. RDS   │
        │   Caddy)    │   │             │    │  Cloud SQL   │
        └─────────────┘   └─────────────┘    └──────────────┘
```

**Key differences from local dev:**
- PostgreSQL runs as a **managed service**, not in a container
- Frontend is **pre-built** (`npm run build`) and served as static files
- **Caddy** (or Nginx) handles SSL termination and reverse proxying
- API runs behind **Gunicorn** for production-grade concurrency

### Why Gunicorn?

Locally you use `uvicorn` — a single-process dev server. In production,
**Gunicorn** manages multiple worker processes so your app can handle several
requests at once and keep running if one worker crashes.

```bash
# Local (single process, for dev)
uv run uvicorn app.main:app --reload

# Production (multi-worker, for deployment)
gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

| Part | Purpose |
|------|---------|
| `--workers 4` | Runs 4 copies of your app — handles 4× the traffic |
| `--worker-class uvicorn` | Uses Uvicorn's async speed inside each worker |
| `--bind` | Listens on port 8000 |

For a 2GB VPS, 4 workers is the sweet spot. You need to add `gunicorn` to
`pyproject.toml` dependencies before deploying.

### Database connection pooling

asyncpg pools connections **per worker process**, so with 4 Gunicorn workers
you get 4 independent pools. On small managed instances (e.g. Cloud SQL
`db-f1-micro`, max 25 connections) that can exhaust the database. Size the
pool explicitly in `backend/app/db/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=5,          # per worker
    max_overflow=2,
    pool_pre_ping=True,   # validate the connection before use (survives DB restarts)
)
```

`pool_pre_ping` matters in production — it re-validates stale sockets after a
database restart instead of letting the first request crash.

---

## 3. Option A — Deploy on a VPS with Docker Compose

Best for: **simplicity**, predictable cost, full control.
Cost: ~£10-25/month.

### Step 1 — Provision a VPS

```bash
# Example using a 2GB RAM Ubuntu VPS from Hetzner or DigitalOcean
# Once you have the IP, SSH in:
ssh root@your-server-ip
```

### Step 2 — Install Docker + Caddy

```bash
# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Caddy
apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy
```

### Step 3 — Set up the database

```bash
# Option A: Use a managed PostgreSQL service (recommended)
#   1. Create a PostgreSQL instance on your cloud provider
#   2. Note the connection string: postgresql+asyncpg://user:pass@host:5432/wealthwise
#   3. Keep it on a private network / restricted IPs — never expose it publicly

# Option B: Run PostgreSQL on the VPS (fine for a personal app, you own backups)
#   ⚠️ Bind to localhost (127.0.0.1), NOT 0.0.0.0, so it's unreachable from the internet
docker run -d \
  --name wealthwise-db \
  -e POSTGRES_USER=wealthwise \
  -e POSTGRES_PASSWORD='<a-real-long-random-password>' \
  -e POSTGRES_DB=wealthwise \
  -v /var/lib/pgdata:/var/lib/postgresql/data \
  -p 127.0.0.1:5432:5432 \
  postgres:17-alpine
```

> ⚠️ **Security rules for the database — in every option:**
> - Use a **strong random password**, never the dev default (`wealthwise/wealthwise`)
> - The DB must be reachable **only by the API** (localhost bind on a VPS, private
>   IP / authorized networks for managed services). Never open port 5432 to the internet.
> - `DATABASE_URL` lives in `.env` / a secret manager — never in the code or committed.

### Step 4 — Clone the repo and configure

```bash
git clone https://github.com/sagarthapa9/wealthwise-v2.git /app/wealthwise-v2
cd /app/wealthwise-v2

# Create production .env
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://wealthwise:secure-password@localhost:5432/wealthwise
DEBUG=false
CORS_ORIGINS=https://wealthwise.example.com
EOF
```

### Step 5 — Build and run with Docker Compose

Migrations must run **before** the new API starts serving traffic — otherwise
the app hits `relation "..." does not exist` errors until they complete.

```bash
# 1. Start the database first (skip if using a managed service — it's external)
docker compose up -d db

# 2. Backup before any migration (self-hosted only — non-negotiable)
docker exec wealthwise-db pg_dump -U wealthwise -d wealthwise > backup_$(date +%Y%m%d).sql

# 3. Apply migrations with the new image, WITHOUT exposing the API yet
docker compose -f docker-compose.yml run --rm api uv run alembic upgrade head

# 4. Only now build and start the API
docker compose -f docker-compose.yml up -d --build api

# 5. Build the frontend for production
cd frontend
npm ci
npm run build
cd ..
```

`docker compose run --rm api` runs a one-off migration container instead of
exec'ing into the running server, so migrations are isolated and don't
partially upgrade while the API is live.

### Step 6 — Configure Caddy as reverse proxy

Create `/etc/caddy/Caddyfile`:

```caddy
wealthwise.example.com {
    # Serve frontend static files
    root * /app/wealthwise-v2/frontend/dist
    try_files {path} index.html

    # Proxy API requests to FastAPI
    handle_path /api/* {
        reverse_proxy localhost:8000
    }

    # Enable auto HTTPS via Let's Encrypt
    tls your-email@example.com
}
```

```bash
# Reload Caddy
systemctl reload caddy
```

### Step 7 — Verify

```bash
curl https://wealthwise.example.com/api/health
# Expected: {"status": "OK", "database": "OK"}
```

Open `https://wealthwise.example.com` in a browser.

---

## 4. Option B — Deploy on Cloud Run + Cloud SQL

Best for: **auto-scaling**, pay-per-use, no server management.
Cost: ~£5-50/month depending on usage.

### Step 1 — Set up Google Cloud Project

```bash
# Install gcloud CLI
# https://cloud.google.com/sdk/docs/install

gcloud auth login
gcloud projects create wealthwise-prod
gcloud config set project wealthwise-prod
gcloud services enable run.googleapis.com sqladmin.googleapis.com
```

### Step 2 — Create a Cloud SQL PostgreSQL instance

```bash
gcloud sql instances create wealthwise-db \
  --database-version=POSTGRES_17 \
  --tier=db-f1-micro \
  --region=europe-west2

gcloud sql databases create wealthwise --instance=wealthwise-db
gcloud sql users create wealthwise --instance=wealthwise-db --password=secure-password
```

### Step 3 — Create a production Dockerfile for the API

Create `Dockerfile.prod`:

```dockerfile
FROM python:3.14-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/
RUN uv sync --frozen --no-dev

# Run with Gunicorn for production concurrency
CMD ["uv", "run", "gunicorn", "app.main:app", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

Add `gunicorn` to `pyproject.toml`:

```toml
dependencies = [
    ...
    "gunicorn>=23.0.0",
]
```

### Step 4 — Deploy the API to Cloud Run

```bash
# Build and push to Artifact Registry
gcloud builds submit --tag europe-west2-docker.pkg.dev/wealthwise-prod/api/wealthwise-api

# Deploy to Cloud Run
gcloud run deploy wealthwise-api \
  --image=europe-west2-docker.pkg.dev/wealthwise-prod/api/wealthwise-api \
  --platform=managed \
  --region=europe-west2 \
  --allow-unauthenticated \
  --add-cloudsql-instances=wealthwise-prod:europe-west2:wealthwise-db \
  --set-env-vars="DATABASE_URL=postgresql+asyncpg://wealthwise:secure-password@localhost:5432/wealthwise?host=/cloudsql/wealthwise-prod:europe-west2:wealthwise-db,DEBUG=false"
```

### Step 5 — Deploy the frontend to Cloud Storage

```bash
cd frontend
npm ci
npm run build

# Upload to a Cloud Storage bucket
gsutil mb gs://wealthwise-frontend
gsutil iam ch allUsers:objectViewer gs://wealthwise-frontend
gsutil cp -r dist/* gs://wealthwise-frontend/
```

### Step 6 — Set up Cloud Load Balancer

```
1. Create a serverless NEG (Network Endpoint Group) pointing to Cloud Run
2. Create a storage bucket backend for static files
3. Set up HTTPS load balancer with:
   - Frontend: static files (/*)
   - API route: /api/* → serverless NEG
4. Provision SSL certificate via Google-managed SSL
5. Point your domain to the load balancer IP
```

### Step 7 — Run migrations

Run the migration **job** and wait for it to succeed **before** deploying the
new service revision. The job must be created with the *new* image (it carries
the new migration files):

```bash
gcloud run jobs create db-migrate \
  --image=europe-west2-docker.pkg.dev/wealthwise-prod/api/wealthwise-api \
  --command="uv run alembic upgrade head" \
  --add-cloudsql-instances=wealthwise-prod:europe-west2:wealthwise-db

gcloud run jobs execute db-migrate
```

Then verify the job ran the expected revision before traffic switches over:

```bash
gcloud run jobs describe db-migrate --format="value(status.conditions)" 
# Expected: Succeeded

# Confirm the DB is at the latest revision
gcloud sql connect wealthwise-db --user=wealthwise --quiet \
  --command="SELECT version_num FROM alembic_version;"
```

---

## 5. Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/wealthwise` |
| `DEBUG` | Enable debug mode (set `false` in prod) | `false` |

### Recommended

| Variable | Description | Example |
|----------|-------------|---------|
| `CORS_ORIGINS` | Comma-separated allowed origins | `https://wealthwise.example.com` |
| `DEEPSEEK_API_KEY` | API key for AI features | (set when deploying AI phase) |

### `.env.prod` template

```bash
DATABASE_URL=postgresql+asyncpg://wealthwise:your-password@your-host:5432/wealthwise
DEBUG=false
CORS_ORIGINS=https://wealthwise.example.com
```

---

## 6. CI/CD Pipeline with GitHub Actions

### Pipeline overview

```
                    ┌─ CI ─────────────────────┐       ┌─ CD ─────────────────┐
                    │                          │       │                      │
  Push to main ────►│  1. Install deps         │       │  6. Build Docker     │
                    │  2. Lint (ruff + eslint)  │──────►│  7. Push to registry│
                    │  3. Type check            │       │  8. Deploy to server │
                    │  4. Run tests             │       │  9. Smoke test       │
                    │  5. Build frontend        │       │                      │
                    └──────────────────────────┘       └──────────────────────┘
```

### File to create

Create `.github/workflows/deploy.yml` in the repo root:

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Lint & Test
    runs-on: ubuntu-latest

    # A throwaway Postgres lets us prove migrations work on a FRESH database
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: wealthwise
          POSTGRES_PASSWORD: wealthwise
          POSTGRES_DB: wealthwise
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U wealthwise"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      # ── Backend checks ──────────────────────────────────
      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          version: "0.6.x"

      - name: Set up Python
        run: uv python install 3.14

      - name: Install backend dependencies
        working-directory: ./backend
        run: uv sync --frozen

      - name: Lint backend (ruff)
        working-directory: ./backend
        run: uv run ruff check . --output-format=github

      # ⚠️ ALWAYS FAILING — a broken migration chain breaks every PR.
      #    This is the test that catches duplicate/conflicting migrations
      #    (e.g. two files adding the same column) which only surface on a
      #    fresh database.
      - name: Run migrations on a fresh database
        working-directory: ./backend
        env:
          DATABASE_URL: postgresql+asyncpg://wealthwise:wealthwise@localhost:5432/wealthwise
        run: |
          uv run alembic upgrade head
          uv run alembic check   # catches model ↔ migration drift

      - name: Run backend tests
        working-directory: ./backend
        run: uv run pytest
        continue-on-error: true  # no tests written yet

      # ── Frontend checks ─────────────────────────────────
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "24"
          cache: "npm"
          cache-dependency-path: ./frontend/package-lock.json

      - name: Install frontend dependencies
        working-directory: ./frontend
        run: npm ci

      - name: Lint frontend (ESLint)
        working-directory: ./frontend
        run: npx eslint src/
        continue-on-error: true

      - name: Build frontend
        working-directory: ./frontend
        run: npm run build

  deploy:
    name: Deploy to Production
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      # ── Build & push Docker image ───────────────────────
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name: Build and push API image
        uses: docker/build-push-action@v6
        with:
          context: ./backend
          file: ./backend/Dockerfile
          push: true
          tags: |
            sagarthapa/wealthwise-api:latest
            sagarthapa/wealthwise-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      # ── Deploy via SSH ──────────────────────────────────
      - name: Deploy to VPS
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /app/wealthwise-v2
            git pull
            docker compose pull api
            # Migrate BEFORE the new API starts — avoids 500s from missing tables
            docker compose run --rm api uv run alembic upgrade head
            docker compose up -d --no-deps api

      # ── Smoke test ──────────────────────────────────────
      - name: Smoke test
        run: |
          sleep 10
          curl -f https://wealthwise.example.com/api/health || exit 1
```

### Setting up GitHub Secrets

Before the pipeline works, add these to your repo:
**Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
|--------|-------|
| `DOCKER_USERNAME` | Your Docker Hub username |
| `DOCKER_PASSWORD` | Docker Hub access token (not your password) |
| `SSH_HOST` | Your VPS IP address |
| `SSH_USER` | SSH username (usually `root`) |
| `SSH_PRIVATE_KEY` | Your SSH private key |

### How the pipeline runs

1. You push to `main` on GitHub
2. GitHub Actions triggers the workflow
3. **CI phase:** Installs deps, lints, tests, builds the frontend
4. **CD phase:** Builds the Docker image, pushes to Docker Hub, SSHes into your VPS, pulls the new image, restarts the API container, runs migrations
5. **Smoke test:** Hits the health endpoint to confirm the deployment worked

### Triggering deploys manually

You can also trigger the workflow manually via the GitHub UI:
**Actions → Deploy → Run workflow → main**

---

## 7. Monitoring & Maintenance

### Health check endpoint

The API has a health check that also pings the database:

```
GET /api/health
Response: {"status": "OK", "database": "OK"}
```

Use this for load balancer health checks or uptime monitoring.

### Uptime monitoring (free)

- **UptimeRobot** — free, checks your endpoint every 5 minutes, alerts via email
- **Pingdom** — more features, free tier available

### Logs

```bash
# Docker logs
docker compose logs api --tail=50 -f

# Cloud Run logs (Option B)
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=wealthwise-api" --limit=20
```

### Database backups

```bash
# For a Docker-hosted database:
docker exec wealthwise-db pg_dump -U wealthwise wealthwise > backup_$(date +%Y%m%d).sql

# For Cloud SQL (automated backups enabled by default):
gcloud sql backups list --instance=wealthwise-db
```

**Scheduled backups (self-hosted only).** Managed databases do this for you;
on a VPS set up a cron job:

```bash
# /etc/cron.d/wealthwise-backup
0 2 * * *  docker exec wealthwise-db pg_dump -U wealthwise wealthwise | gzip > /var/backups/wealthwise_$(date +\%F).sql.gz
```

Keep ~30 days and **test a restore at least once**. A backup you've never
restored is a guess. To test: create a throwaway container, load the dump,
and confirm the tables + row counts match:

```bash
docker run -d --name restore-test \
  -e POSTGRES_USER=wealthwise -e POSTGRES_PASSWORD=x -e POSTGRES_DB=wealthwise \
  -v /var/backups:/backups postgres:17-alpine
docker exec restore-test psql -U wealthwise -d wealthwise -f /backups/wealthwise_YYYY-MM-DD.sql.gz
# confirm, then: docker rm -f restore-test
```

### Database monitoring

Monitor these three things at minimum — they fail quietly and take the whole
app down:

```bash
# 1. Disk space on the DB volume (Postgres dies when full)
df -h /var/lib/pgdata        # self-hosted
gcloud sql instances describe wealthwise-db --format="value(diskUsageGb)"  # Cloud SQL

# 2. Connection count — the #1 sign your pool is mis-sized
docker exec wealthwise-db psql -U wealthwise -d wealthwise -c "SELECT count(*) FROM pg_stat_activity;"

# 3. Which revision production is on
docker exec wealthwise-db psql -U wealthwise -d wealthwise -c "SELECT version_num FROM alembic_version;"
```

### Updating the application

Same ordering as first deploy — **migrate, then start the new API**:

```bash
# Manual update on a VPS:
ssh user@host
cd /app/wealthwise-v2
git pull
docker compose pull api
docker compose run --rm api uv run alembic upgrade head
docker compose up -d --no-deps api
```

### Rollback

```bash
# Rollback to a previous Docker image tag:
docker compose -f docker-compose.yml up -d api sagarthapa/wealthwise-api:previous-tag
```

---

## 8. Database Migration & Deployment Best Practices

These rules come from real incidents on this project — including a duplicate
migration (`c6d7e8f9a0b1`) that added the `archived` column a second time and
broke every fresh database while dev machines stayed healthy.

### Rule 1 — Migrate BEFORE the new code serves traffic

The new app version queries columns that don't exist until the migration runs,
so migrating first prevents a window of 500s. See §3 Step 5, §4 Step 7, §6
deploy step, and §7 "Updating the application" — all follow this ordering.

### Rule 2 — Prove the chain works on a FRESH database

Alembic tracks state by revision ID, not by schema content. A migration that
"passes" on your dev DB (because it was already applied there) can still break
on a fresh one. Before every deploy, run the chain from zero:

```bash
# Local: wipe + re-migrate — the exact test that catches duplicate columns
docker compose down -v && docker compose up -d db
docker compose exec api uv run alembic upgrade head
```

In CI this runs automatically on every PR (see §6 "Run migrations on a fresh
database").

### Rule 3 — Never edit an already-applied migration

Once a migration has been committed and run anywhere, it is frozen. Editing it
only changes behaviour on *fresh* databases — dev machines that already ran it
will silently diverge from everyone else. For any follow-up change, write a
**new** migration:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
# review the generated file, then upgrade
uv run alembic upgrade head
```

### Rule 4 — Two migrations must never touch the same column

Before generating a migration, check what the chain already does:

```bash
uv run alembic history          # the full chain
uv run alembic current          # where this DB is
```

If a column already exists, extend the latest migration's `upgrade()` instead
of adding a duplicate `add_column` for it.

### Rule 5 — Back up before you migrate

```bash
docker exec wealthwise-db pg_dump -U wealthwise -d wealthwise > backup_$(date +%Y%m%d).sql
```

Especially for destructive migrations (`drop_column`, `drop_table`).

### Rule 6 — Have a rollback plan

```bash
# Downgrade one step (needs the OLD image still present, and the migration
# must implement downgrade()):
docker compose run --rm api uv run alembic downgrade -1

# Preferred: restore the pre-migration backup from §7
```

Never rely on `downgrade()` for a release you don't control — a restore from
backup is the dependable fallback.

### Rule 7 — Check for drift between models and migrations

```bash
uv run alembic check
```

Fails if the SQLAlchemy models and the migration chain disagree — catches the
case where a column was added to a model but no migration was written.

### Sanity checklist before any production migration

```bash
1.  uv run alembic history        # understand the chain
2.  docker compose down -v && up  # prove it works on a fresh DB
3.  uv run alembic check          # model ↔ migration drift
4.  pg_dump backup                # safety net
5.  migrate → verify → deploy     # correct ordering (Rule 1)
6.  alembic current on prod       # confirm the revision
```

---

## Quick Reference — Commands Cheat Sheet

```bash
# ── Local ─────────────────────────────────────────────────
docker compose up --build           # Start everything
docker compose exec api uv run alembic upgrade head  # Run migrations
docker compose down -v && docker compose up -d db && docker compose exec api uv run alembic upgrade head  # Fresh-DB migration test

# ── VPS Deploy ────────────────────────────────────────────
scp .env root@host:/app/wealthwise-v2/.env
ssh root@host "cd /app/wealthwise-v2 && docker compose up -d db && docker compose run --rm api uv run alembic upgrade head && docker compose up -d --build"

# ── CI/CD ─────────────────────────────────────────────────
git add -A && git commit -m "message" && git push
# Pipeline runs automatically on push to main

# ── Production checks ─────────────────────────────────────
curl https://wealthwise.example.com/api/health
docker compose logs api --tail=20
```
