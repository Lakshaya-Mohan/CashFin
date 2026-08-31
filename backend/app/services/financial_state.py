from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.account import Account
from app.models.payable import Payable
from app.models.receivable import Receivable
from app.schemas.financial_state import FinancialState, UpcomingPayable, UpcomingReceivable


class FinancialStateService:
    @staticmethod
    def get_financial_state(session: Session, company_id: int, as_of_date: date) -> FinancialState:
        # Calculate current cash
        accounts = session.execute(
            select(Account).where(Account.company_id == company_id)
        ).scalars().all()
        
        current_cash = sum((acc.current_balance for acc in accounts), Decimal('0.00'))

        # Calculate pending payables
        payables = session.execute(
            select(Payable)
            .where(Payable.company_id == company_id, Payable.status == "PENDING")
            .order_by(Payable.due_date)
        ).scalars().all()

        pending_payables_total = sum((p.amount for p in payables), Decimal('0.00'))
        
        upcoming_payables = [
            UpcomingPayable(
                id=p.id,
                amount=p.amount,
                due_date=p.due_date,
                description=p.description
            ) for p in payables
        ]

        # Calculate expected receivables
        receivables = session.execute(
            select(Receivable)
            .where(Receivable.company_id == company_id, Receivable.status.in_(["EXPECTED", "DELAYED"]))
            .order_by(Receivable.expected_date)
        ).scalars().all()

        pending_receivables_total_raw = sum((r.amount for r in receivables), Decimal('0.00'))
        pending_receivables_total_adjusted = sum(
            (r.amount * r.confidence for r in receivables), Decimal('0.00')
        )
        
        upcoming_receivables = [
            UpcomingReceivable(
                id=r.id,
                amount=r.amount,
                expected_date=r.expected_date,
                confidence=r.confidence,
                description=r.description
            ) for r in receivables
        ]

        return FinancialState(
            company_id=company_id,
            as_of_date=as_of_date,
            current_cash=current_cash,
            pending_payables_total=pending_payables_total,
            pending_receivables_total_raw=pending_receivables_total_raw,
            pending_receivables_total_adjusted=pending_receivables_total_adjusted,
            upcoming_payables=upcoming_payables,
            upcoming_receivables=upcoming_receivables
        )
