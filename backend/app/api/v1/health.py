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
