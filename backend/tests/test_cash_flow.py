import pytest
from datetime import date
from decimal import Decimal

from app.schemas.financial_state import (
    FinancialState, 
    UpcomingPayable, 
    UpcomingReceivable, 
    ProjectionMode,
    EventType
)
from app.services.cash_flow import CashFlowService

@pytest.fixture
def base_state():
    return FinancialState(
        company_id=1,
        as_of_date=date(2026, 9, 1),
        current_cash=Decimal('1000.00'),
        pending_payables_total=Decimal('0.00'),
        pending_receivables_total_raw=Decimal('0.00'),
        pending_receivables_total_adjusted=Decimal('0.00'),
        upcoming_payables=[],
        upcoming_receivables=[]
    )

def test_1_cash_sufficient_for_all_obligations(base_state):
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero is None
    assert projection.days_to_buffer_breach is None
    assert len(projection.shortfalls) == 0

def test_2_cash_negative_before_next_receivable(base_state):
    base_state.current_cash = Decimal('100.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5))
    ]
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('500.00'), expected_date=date(2026, 9, 10), confidence=Decimal('1.0'))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero == 4 # 9/5 is 4 days from 9/1
    assert projection.projected_balances[date(2026, 9, 5)] == Decimal('-100.00')

def test_3_receivable_arrives_before_obligation(base_state):
    base_state.current_cash = Decimal('100.00')
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('500.00'), expected_date=date(2026, 9, 2), confidence=Decimal('1.0'))
    ]
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero is None

def test_4_receivable_arrives_after_obligation(base_state):
    base_state.current_cash = Decimal('100.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5))
    ]
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('500.00'), expected_date=date(2026, 9, 6), confidence=Decimal('1.0'))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero == 4

def test_5_multiple_events_same_date(base_state):
    base_state.current_cash = Decimal('100.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5)),
        UpcomingPayable(id=2, amount=Decimal('300.00'), due_date=date(2026, 9, 5))
    ]
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('400.00'), expected_date=date(2026, 9, 5), confidence=Decimal('1.0'))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    
    # Sorting deterministic: Date, Inflow first, then source_id
    assert projection.events[0].event_type == EventType.INFLOW
    assert projection.events[1].event_type == EventType.OUTFLOW
    assert projection.events[2].event_type == EventType.OUTFLOW

    # Total flow on day 5: +400 -200 -300 = -100
    # Day 5 final balance: 100 - 100 = 0
    # It hits exactly zero. The exact zero doesn't trigger "days_to_zero < 0", because it requires `< 0` based on requirements (`projected_cash < 0` for shortfall). Wait, requirements say: `cash reaching exactly zero` vs `cash becoming negative`. If `< 0` is breach, then it should not breach.
    assert projection.days_to_zero is None

def test_6_multiple_accounts_contribute(base_state):
    # This is tested in FinancialStateService primarily, but we can verify base cash here
    base_state.current_cash = Decimal('500.00') + Decimal('500.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('800.00'), due_date=date(2026, 9, 5))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero is None

def test_7_no_future_receivables(base_state):
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('2000.00'), due_date=date(2026, 9, 5))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero == 4

def test_8_no_pending_payables(base_state):
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('500.00'), expected_date=date(2026, 9, 5), confidence=Decimal('1.0'))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero is None
    assert len(projection.shortfalls) == 0

def test_9_cash_never_reaches_zero(base_state):
    base_state.current_cash = Decimal('10000.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('2000.00'), due_date=date(2026, 9, 5)),
        UpcomingPayable(id=2, amount=Decimal('1000.00'), due_date=date(2026, 9, 10))
    ]
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'))
    assert projection.days_to_zero is None

def test_10_minimum_cash_buffer_breached(base_state):
    base_state.current_cash = Decimal('1000.00')
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('200.00'), due_date=date(2026, 9, 5))
    ]
    # Balance becomes 800. Buffer is 900.
    projection = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('900.00'))
    assert projection.days_to_zero is None
    assert projection.days_to_buffer_breach == 4
    
    breaches = projection.shortfalls
    assert len(breaches) == 1
    assert breaches[0].shortfall_amount == Decimal('100.00')
    assert not breaches[0].is_zero_breach

def test_confidence_adjusted_mode(base_state):
    base_state.upcoming_receivables = [
        UpcomingReceivable(id=1, amount=Decimal('1000.00'), expected_date=date(2026, 9, 2), confidence=Decimal('0.5'))
    ]
    base_state.upcoming_payables = [
        UpcomingPayable(id=1, amount=Decimal('1200.00'), due_date=date(2026, 9, 5))
    ]
    
    # Mode RAW: +1000 -> 2000 - 1200 -> 800 (No zero breach)
    raw_proj = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'), projection_mode=ProjectionMode.RAW)
    assert raw_proj.days_to_zero is None
    
    # Mode CONFIDENCE_ADJUSTED: +500 -> 1500 - 1200 -> 300 (Still no zero breach, but value is different)
    adj_proj = CashFlowService.calculate_projection(base_state, minimum_cash_buffer=Decimal('0.00'), projection_mode=ProjectionMode.CONFIDENCE_ADJUSTED)
    assert adj_proj.projected_balances[date(2026, 9, 5)] == Decimal('300.00')
