from datetime import date
from decimal import Decimal
from typing import List

from app.schemas.financial_state import (
    FinancialState, 
    CashFlowProjection, 
    CashFlowEvent, 
    EventType, 
    ProjectionMode,
    BreachEvent
)

class CashFlowService:
    @staticmethod
    def calculate_projection(
        state: FinancialState, 
        minimum_cash_buffer: Decimal = Decimal('0.00'),
        projection_mode: ProjectionMode = ProjectionMode.RAW
    ) -> CashFlowProjection:
        
        events: List[CashFlowEvent] = []
        
        # 1. Normalize Payables into OUTFLOW events
        for p in state.upcoming_payables:
            events.append(CashFlowEvent(
                date=p.due_date,
                amount=-p.amount,
                event_type=EventType.OUTFLOW,
                source_id=p.id,
                description=p.description
            ))
            
        # 2. Normalize Receivables into INFLOW events
        for r in state.upcoming_receivables:
            amount = r.amount if projection_mode == ProjectionMode.RAW else (r.amount * r.confidence)
            events.append(CashFlowEvent(
                date=r.expected_date,
                amount=amount,
                event_type=EventType.INFLOW,
                source_id=r.id,
                description=r.description
            ))
            
        # 3. Sort chronologically
        # To make deterministic, sort by date, then amount (inflows before outflows if same amount magnitude doesn't apply directly but let's just use amount), then source_id
        events.sort(key=lambda x: (x.date, x.event_type == EventType.OUTFLOW, x.source_id))

        # 4. Calculate projections
        projected_balances: dict[date, Decimal] = {}
        shortfalls: List[BreachEvent] = []
        days_to_zero = None
        days_to_buffer_breach = None
        
        current_balance = state.current_cash
        # If starting balance is already below buffer
        if current_balance < minimum_cash_buffer and days_to_buffer_breach is None:
            days_to_buffer_breach = 0
            shortfalls.append(BreachEvent(
                breach_date=state.as_of_date,
                projected_balance=current_balance,
                shortfall_amount=minimum_cash_buffer - current_balance,
                is_zero_breach=False
            ))
        if current_balance < 0 and days_to_zero is None:
            days_to_zero = 0
            shortfalls.append(BreachEvent(
                breach_date=state.as_of_date,
                projected_balance=current_balance,
                shortfall_amount=abs(current_balance),
                is_zero_breach=True
            ))

        for event in events:
            current_balance += event.amount
            # Overwrite the balance for the day (last event on that day will be the final balance)
            projected_balances[event.date] = current_balance
            
            days_diff = (event.date - state.as_of_date).days
            # Ensure days is non-negative if event is in the past, but usually it shouldn't be negative in a real projection, but we track strictly.
            if days_diff < 0:
                days_diff = 0
                
            # Check buffer breach
            if current_balance < minimum_cash_buffer:
                if days_to_buffer_breach is None:
                    days_to_buffer_breach = days_diff
                shortfalls.append(BreachEvent(
                    breach_date=event.date,
                    projected_balance=current_balance,
                    shortfall_amount=minimum_cash_buffer - current_balance,
                    triggering_event=event,
                    is_zero_breach=False
                ))
                
            # Check zero breach
            if current_balance < 0:
                if days_to_zero is None:
                    days_to_zero = days_diff
                shortfalls.append(BreachEvent(
                    breach_date=event.date,
                    projected_balance=current_balance,
                    shortfall_amount=abs(current_balance),
                    triggering_event=event,
                    is_zero_breach=True
                ))

        return CashFlowProjection(
            as_of_date=state.as_of_date,
            starting_balance=state.current_cash,
            minimum_cash_buffer=minimum_cash_buffer,
            projection_mode=projection_mode,
            events=events,
            projected_balances=projected_balances,
            days_to_zero=days_to_zero,
            days_to_buffer_breach=days_to_buffer_breach,
            shortfalls=shortfalls
        )
