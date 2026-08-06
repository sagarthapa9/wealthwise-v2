from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings

app = FastAPI(
    title="WealthWise API",
    version="0.1.0",
    description="AI-powered investment analysis backend",
)

# CORS — same-origin traffic (dev proxy, Caddy) is unaffected; this is needed
# only when the frontend and API live on different origins (e.g. Cloud Run).
# An empty CORS_ORIGINS denies all cross-origin requests (safe default).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
    return {"status": "OK"}
