from fastapi import APIRouter

from app.api.routes.companies import router as companies_router
from app.api.routes.decisions import router as decisions_router
from app.api.routes.financial_state import router as financial_state_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.cash_flow import router as cash_flow_router
from app.api.routes.health import router as health_router
from app.api.routes.ingestion import router as ingestion_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(companies_router)
api_router.include_router(financial_state_router)
api_router.include_router(cash_flow_router)
api_router.include_router(forecast_router)
api_router.include_router(decisions_router)
api_router.include_router(ingestion_router)
