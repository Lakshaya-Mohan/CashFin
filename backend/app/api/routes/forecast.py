from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.company import Company
from app.models.account import Account
from app.models.transaction import Transaction
from app.schemas.forecast import CashFlowForecast
from app.services.forecast_service import ForecastService

router = APIRouter(prefix="/companies", tags=["Forecast"])


@router.get(
    "/{company_id}/forecast",
    response_model=CashFlowForecast,
    summary="Get cash-flow forecast",
    description="Retrieves ML-predicted future cash flows for a company.",
)
def get_forecast(
    company_id: int,
    horizon_days: int = Query(default=30, ge=1, le=90, description="Forecast horizon (1-90 days)"),
    db: Session = Depends(get_db),
):
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    svc = ForecastService()
    if not svc.forecaster.load_model():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast unavailable: model has not been trained."
        )

    accounts = db.execute(select(Account.id).where(Account.company_id == company_id)).scalars().all()
    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast unavailable: no accounts found for company."
        )

    txns = db.execute(select(Transaction).where(Transaction.account_id.in_(accounts))).scalars().all()
    if not txns:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Forecast unavailable: insufficient historical transactions."
        )

    df_txns = pd.DataFrame([
        {
            "transaction_date": t.transaction_date,
            "amount": float(t.amount),
            "transaction_type": t.transaction_type,
        }
        for t in txns
    ])

    try:
        forecast = svc.generate_forecast(df_txns, company_id, horizon_days)
        return forecast
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Forecast unavailable: {str(e)}"
        )
