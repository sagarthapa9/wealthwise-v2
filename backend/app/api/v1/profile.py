"""Profile endpoint — manage investor personal context."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileResponse, ProfileUpdate

router = APIRouter(tags=["profile"])


async def _get_or_create_profile(db: AsyncSession) -> Profile:
    """Return the existing profile, or create one with defaults."""
    result = await db.execute(select(Profile).limit(1))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile()
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    """Get the user's profile. Auto-creates with defaults if none exists."""
    profile = await _get_or_create_profile(db)
    return profile


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    data: ProfileUpdate, db: AsyncSession = Depends(get_db)
):
    """Create or update the user's profile."""
    profile = await _get_or_create_profile(db)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    await db.commit()
    await db.refresh(profile)
    return profile
