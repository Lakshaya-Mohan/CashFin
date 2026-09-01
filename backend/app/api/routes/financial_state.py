from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.company import Company
from app.schemas.financial_state import FinancialState, ReceivableMode
from app.services.financial_state import FinancialStateService

router = APIRouter(prefix="/companies", tags=["Financial State"])


@router.get(
    "/{company_id}/financial-state",
    response_model=FinancialState,
    summary="Get financial state",
    description="Retrieves the consolidated financial state for a company as of a specified date.",
)
def get_financial_state(
    company_id: int,
    as_of_date: Optional[date] = Query(default=None, description="As-of date for financial state"),
    receivable_mode: ReceivableMode = Query(
        default=ReceivableMode.RAW, description="RAW face value or CONFIDENCE_ADJUSTED value"
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
    return state
