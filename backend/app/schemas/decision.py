from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum

from app.schemas.financial_state import ReceivableMode


class ActionType(str, Enum):
    PAY = "PAY"
    DEFER = "DEFER"
    NEGOTIATE = "NEGOTIATE"


class Obligation(BaseModel):
    """
    Input schema for a single obligation entering the Decision Engine.
    Maps to a Payable record but is decoupled from the ORM layer.
    """
    payable_id: int
    counterparty_id: int
    counterparty_name: str
    amount: Decimal
    due_date: date
    urgency: int       # 1–5: how time-critical is this payment
    penalty_risk: int  # 1–5: consequence of non-payment
    flexibility: int   # 1–5: can the counterparty accept rescheduling
    status: str = "PENDING"
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DecisionFactor(BaseModel):
    """
    A single structured factor used to justify a decision.
    Allows human-readable explanation without embedding prose in the algorithm.
    """
    factor_name: str
    raw_value: int
    weight: float
    contribution: float  # weight * raw_value (negative for inverse factors)

    model_config = ConfigDict(from_attributes=True)


class TimelineEntry(BaseModel):
    """
    A single step in the chronological cash-flow simulation for the selected strategy.
    Allows full auditability of the decision.
    """
    event_date: date
    description: str
    event_type: str    # "INFLOW" or "OUTFLOW"
    amount: Decimal
    cash_before: Decimal
    cash_after: Decimal

    model_config = ConfigDict(from_attributes=True)


class ObligationDecision(BaseModel):
    """
    The recommended action for a single obligation, with structured justification.
    """
    obligation: Obligation
    action: ActionType
    deferral_cost: Optional[float] = None  # None if action is PAY
    decision_factors: List[DecisionFactor] = []
    reasoning: str = ""

    model_config = ConfigDict(from_attributes=True)


class DecisionResult(BaseModel):
    """
    The complete structured output of the Decision Engine.

    Note: All recommendations in this result are SUGGESTED actions only.
    No payment has been executed. No counterparty has been notified.
    """
    feasible: bool
    as_of_date: date
    receivable_mode: ReceivableMode

    initial_cash: Decimal
    minimum_cash_buffer: Decimal
    total_obligations: Decimal
    total_expected_inflows: Decimal

    selected_obligations: List[ObligationDecision] = []
    deferred_obligations: List[ObligationDecision] = []
    negotiated_obligations: List[ObligationDecision] = []

    ending_cash: Decimal
    minimum_projected_cash: Decimal
    date_of_minimum_projected_cash: Optional[date] = None
    projected_shortfall: Optional[Decimal] = None  # None means no shortfall detected

    total_deferral_cost: float

    # Full chronological simulation of the selected strategy for audit purposes
    timeline: List[TimelineEntry] = []

    model_config = ConfigDict(from_attributes=True)
