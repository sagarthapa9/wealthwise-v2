from fastapi import FastAPI
from app.api.v1.router import api_v1_router

app = FastAPI(
    title="WealthWise API",
    version="0.1.0",
    description="AI-powered investment analysis backend",
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/api/health")
async def health_check():
    return {"status": "OK"}
