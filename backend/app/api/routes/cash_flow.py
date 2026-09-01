from datetime import date
from decimal import Decimal
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.company import Company
from app.models.transaction import Transaction
from app.models.account import Account
from app.schemas.financial_state import (
    CashFlowProjection,
    ForecastMode,
    ReceivableMode,
)
from app.services.cash_flow import CashFlowService
from app.services.financial_state import FinancialStateService
from app.services.forecast_service import ForecastService

router = APIRouter(prefix="/companies", tags=["Cash Flow"])


@router.get(
    "/{company_id}/cash-flow",
    response_model=CashFlowProjection,
    summary="Get cash-flow projection",
    description="Calculates a chronological cash-flow projection incorporating known and predicted events.",
)
def get_cash_flow_projection(
    company_id: int,
    as_of_date: Optional[date] = Query(default=None, description="Projection starting date"),
    horizon_days: int = Query(default=30, ge=1, le=90, description="Forecast horizon (1-90 days)"),
    minimum_cash_buffer: Decimal = Query(
        default=Decimal("0.00"), ge=Decimal("0.00"), description="Minimum cash buffer floor"
    ),
    receivable_mode: ReceivableMode = Query(
        default=ReceivableMode.RAW, description="Receivable adjustment mode"
    ),
    forecast_mode: ForecastMode = Query(
        default=ForecastMode.CONFIRMED_ONLY, description="Forecasting inclusion mode"
    ),
    db: Session = Depends(get_db),
):
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    target_date = as_of_date or date.today()
    state = FinancialStateService.get_financial_state(db, company_id, target_date)

    forecast = None
    if forecast_mode != ForecastMode.CONFIRMED_ONLY:
        # Load transactions for company
        accounts = db.execute(select(Account.id).where(Account.company_id == company_id)).scalars().all()
        if accounts:
            txns = db.execute(
                select(Transaction).where(Transaction.account_id.in_(accounts))
            ).scalars().all()
            if txns:
                df_txns = pd.DataFrame([
                    {
                        "transaction_date": t.transaction_date,
                        "amount": float(t.amount),
                        "transaction_type": t.transaction_type,
                    }
                    for t in txns
                ])
                try:
                    svc = ForecastService()
                    if svc.forecaster.load_model():
                        forecast = svc.generate_forecast(df_txns, company_id, horizon_days)
                except Exception:
                    forecast = None

    projection = CashFlowService.calculate_projection(
        state=state,
        minimum_cash_buffer=minimum_cash_buffer,
        receivable_mode=receivable_mode,
        forecast_mode=forecast_mode,
        forecast=forecast,
    )
    return projection
