from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.ticker import router as ticker_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.allocations import router as allocations_router
from app.api.v1.profile import router as profile_router
from app.api.v1.accounts import router as accounts_router
from app.api.v1.chat import router as chat_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(ticker_router)
api_v1_router.include_router(portfolio_router)
api_v1_router.include_router(allocations_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(chat_router)
