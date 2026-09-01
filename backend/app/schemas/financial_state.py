from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum

class ReceivableMode(str, Enum):
    RAW = "RAW"
    CONFIDENCE_ADJUSTED = "CONFIDENCE_ADJUSTED"

class ForecastMode(str, Enum):
    CONFIRMED_ONLY = "CONFIRMED_ONLY"
    FORECAST_INCLUDED = "FORECAST_INCLUDED"
    CONSERVATIVE = "CONSERVATIVE"

class EventType(str, Enum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"

class CashFlowEvent(BaseModel):
    date: date
    amount: Decimal
    event_type: EventType
    source_id: int
    description: Optional[str] = None
    is_predicted: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class BreachEvent(BaseModel):
    breach_date: date
    projected_balance: Decimal
    shortfall_amount: Decimal
    triggering_event: Optional[CashFlowEvent] = None
    is_zero_breach: bool = False
    
    model_config = ConfigDict(from_attributes=True)

class UpcomingPayable(BaseModel):
    id: int
    amount: Decimal
    due_date: date
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UpcomingReceivable(BaseModel):
    id: int
    amount: Decimal
    expected_date: date
    confidence: Decimal
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class FinancialState(BaseModel):
    company_id: int
    as_of_date: date
    current_cash: Decimal
    pending_payables_total: Decimal
    pending_receivables_total_raw: Decimal
    pending_receivables_total_adjusted: Decimal
    
    upcoming_payables: List[UpcomingPayable] = []
    upcoming_receivables: List[UpcomingReceivable] = []

    model_config = ConfigDict(from_attributes=True)

class CashFlowProjection(BaseModel):
    as_of_date: date
    starting_balance: Decimal
    minimum_cash_buffer: Decimal
    receivable_mode: ReceivableMode
    forecast_mode: ForecastMode = ForecastMode.CONFIRMED_ONLY
    
    events: List[CashFlowEvent] = []
    projected_balances: dict[date, Decimal] = {}
    
    days_to_zero: Optional[int] = None
    days_to_buffer_breach: Optional[int] = None
    
    shortfalls: List[BreachEvent] = []
    minimum_projected_balance: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)
