from datetime import date
from decimal import Decimal
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.company import Company
from app.models.payable import Payable
from app.models.receivable import Receivable
from app.schemas.decision import DecisionRequest, DecisionResult, Obligation
from app.schemas.financial_state import UpcomingReceivable, ForecastMode, ReceivableMode
from app.services.decision_engine import DecisionEngine
from app.services.financial_state import FinancialStateService

router = APIRouter(prefix="/companies", tags=["Decisions"])


@router.get(
    "/{company_id}/decision",
    response_model=DecisionResult,
    summary="Evaluate obligation payment decision (GET)",
    description="Evaluates payment strategy for pending obligations using query parameters.",
)
def evaluate_decision_get(
    company_id: int,
    as_of_date: date = date.today(),
    minimum_cash_buffer: Decimal = Decimal("0.00"),
    receivable_mode: ReceivableMode = ReceivableMode.RAW,
    forecast_mode: ForecastMode = ForecastMode.CONFIRMED_ONLY,
    db: Session = Depends(get_db),
):
    req = DecisionRequest(
        as_of_date=as_of_date,
        minimum_cash_buffer=minimum_cash_buffer,
        receivable_mode=receivable_mode,
        forecast_mode=forecast_mode.value if isinstance(forecast_mode, ForecastMode) else str(forecast_mode),
    )
    return run_decision_evaluation(company_id, req, db)


@router.post(
    "/{company_id}/decision",
    response_model=DecisionResult,
    summary="Evaluate obligation payment decision (POST)",
    description="Evaluates optimal payment strategy for pending obligations. Read-only: does not execute payments.",
)
def evaluate_decision_post(
    company_id: int,
    request: DecisionRequest,
    db: Session = Depends(get_db),
):
    return run_decision_evaluation(company_id, request, db)


def run_decision_evaluation(company_id: int, request: DecisionRequest, db: Session) -> DecisionResult:
    company = db.execute(select(Company).where(Company.id == company_id)).scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found"
        )

    if request.minimum_cash_buffer < Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Minimum cash buffer cannot be negative."
        )

    target_date = request.as_of_date or date.today()
    state = FinancialStateService.get_financial_state(db, company_id, target_date)

    # Fetch payables and build Obligation list
    payables = db.execute(
        select(Payable)
        .where(Payable.company_id == company_id, Payable.status == "PENDING")
        .order_by(Payable.due_date)
    ).scalars().all()

    obligations: List[Obligation] = []
    for p in payables:
        cp_name = p.counterparty.name if p.counterparty else f"Vendor #{p.counterparty_id}"
        obligations.append(
            Obligation(
                payable_id=p.id,
                counterparty_id=p.counterparty_id,
                counterparty_name=cp_name,
                amount=p.amount,
                due_date=p.due_date,
                urgency=p.urgency if hasattr(p, "urgency") and p.urgency is not None else 3,
                penalty_risk=p.penalty_risk if hasattr(p, "penalty_risk") and p.penalty_risk is not None else 3,
                flexibility=p.flexibility if hasattr(p, "flexibility") and p.flexibility is not None else 3,
                status=p.status,
                description=p.description,
            )
        )

    # Fetch receivables
    receivables_db = db.execute(
        select(Receivable)
        .where(Receivable.company_id == company_id, Receivable.status.in_(["EXPECTED", "DELAYED"]))
        .order_by(Receivable.expected_date)
    ).scalars().all()

    receivables: List[UpcomingReceivable] = [
        UpcomingReceivable(
            id=r.id,
            amount=r.amount,
            expected_date=r.expected_date,
            confidence=r.confidence,
            description=r.description,
        )
        for r in receivables_db
    ]

    engine = DecisionEngine()
    result = engine.evaluate_obligations(
        current_cash=state.current_cash,
        minimum_cash_buffer=request.minimum_cash_buffer,
        obligations=obligations,
        receivables=receivables,
        as_of_date=target_date,
        receivable_mode=request.receivable_mode,
    )
    return result
