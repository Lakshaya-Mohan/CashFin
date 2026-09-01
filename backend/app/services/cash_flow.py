"""
CashFin CashFlowService — Stage 5 update

Integrates ML-predicted cash-flow events alongside confirmed known events
based on the active ForecastMode.

ForecastMode semantics
----------------------
CONFIRMED_ONLY:     Use only known payables and receivables (original behaviour).
FORECAST_INCLUDED:  Append predicted events at their predicted_amount.
CONSERVATIVE:       Append predicted events at conservative_amount
                    (inflow: max(0, predicted - MAE), outflow: predicted + MAE).
                    Clearly labelled as approximate — not a statistically
                    valid prediction interval.

The deterministic DecisionEngine is never modified and always operates on the
events list produced here.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.schemas.financial_state import (
    FinancialState,
    CashFlowProjection,
    CashFlowEvent,
    EventType,
    ReceivableMode,
    ForecastMode,
    BreachEvent,
)
from app.schemas.forecast import CashFlowForecast


class CashFlowService:
    @staticmethod
    def calculate_projection(
        state: FinancialState,
        minimum_cash_buffer: Decimal = Decimal("0.00"),
        receivable_mode: ReceivableMode = ReceivableMode.RAW,
        forecast_mode: ForecastMode = ForecastMode.CONFIRMED_ONLY,
        forecast: Optional[CashFlowForecast] = None,
    ) -> CashFlowProjection:
        """
        Build a chronological cash-flow projection.

        Parameters
        ----------
        state               : Current financial state (payables, receivables, balance).
        minimum_cash_buffer : Cash buffer threshold for breach detection.
        receivable_mode     : RAW uses face value; CONFIDENCE_ADJUSTED applies confidence.
        forecast_mode       : Controls whether ML predictions are included.
        forecast            : Optional CashFlowForecast from ForecastService.
                              Required (but ignored in CONFIRMED_ONLY) when mode
                              is FORECAST_INCLUDED or CONSERVATIVE.
        """
        events: List[CashFlowEvent] = []

        # ── 1. Known payables → OUTFLOW events ────────────────────────────────
        for p in state.upcoming_payables:
            events.append(
                CashFlowEvent(
                    date=p.due_date,
                    amount=-p.amount,
                    event_type=EventType.OUTFLOW,
                    source_id=p.id,
                    description=p.description,
                    is_predicted=False,
                )
            )

        # ── 2. Known receivables → INFLOW events ──────────────────────────────
        for r in state.upcoming_receivables:
            amount = (
                r.amount
                if receivable_mode == ReceivableMode.RAW
                else (r.amount * r.confidence)
            )
            events.append(
                CashFlowEvent(
                    date=r.expected_date,
                    amount=amount,
                    event_type=EventType.INFLOW,
                    source_id=r.id,
                    description=r.description,
                    is_predicted=False,
                )
            )

        # ── 3. ML-predicted events (FORECAST_INCLUDED / CONSERVATIVE) ─────────
        if forecast_mode != ForecastMode.CONFIRMED_ONLY and forecast is not None:
            for i, fe in enumerate(forecast.events):
                if forecast_mode == ForecastMode.CONSERVATIVE:
                    # conservative_amount is pre-computed by ForecastService
                    amount = fe.conservative_amount if fe.conservative_amount is not None else fe.predicted_amount
                else:
                    # FORECAST_INCLUDED — use predicted amount as-is
                    amount = fe.predicted_amount

                # Convert net flow into signed amount:
                # Positive net flow → INFLOW; negative → OUTFLOW
                if amount >= 0:
                    event_type = EventType.INFLOW
                    signed_amount = amount
                else:
                    event_type = EventType.OUTFLOW
                    signed_amount = amount  # already negative

                events.append(
                    CashFlowEvent(
                        # Use a large negative source_id to avoid collisions with real IDs
                        source_id=-(i + 1),
                        date=fe.date,
                        amount=signed_amount,
                        event_type=event_type,
                        description=(
                            f"[PREDICTED] Net flow ({fe.model_name} v{fe.model_version})"
                            + (
                                f" ± ₹{fe.historical_mae:.0f} MAE"
                                if fe.historical_mae is not None
                                else ""
                            )
                        ),
                        is_predicted=True,
                    )
                )

        # ── 4. Sort chronologically (inflows before outflows on same date) ─────
        events.sort(key=lambda x: (x.date, x.event_type == EventType.OUTFLOW, x.source_id))

        # ── 5. Walk the timeline and detect breaches ──────────────────────────
        projected_balances: dict[date, Decimal] = {}
        shortfalls: List[BreachEvent] = []
        days_to_zero: Optional[int] = None
        days_to_buffer_breach: Optional[int] = None

        current_balance = state.current_cash

        # Check initial position
        if current_balance < minimum_cash_buffer:
            days_to_buffer_breach = 0
            shortfalls.append(
                BreachEvent(
                    breach_date=state.as_of_date,
                    projected_balance=current_balance,
                    shortfall_amount=minimum_cash_buffer - current_balance,
                    is_zero_breach=False,
                )
            )
        if current_balance < 0:
            days_to_zero = 0
            shortfalls.append(
                BreachEvent(
                    breach_date=state.as_of_date,
                    projected_balance=current_balance,
                    shortfall_amount=abs(current_balance),
                    is_zero_breach=True,
                )
            )

        for event in events:
            current_balance += event.amount
            projected_balances[event.date] = current_balance

            days_diff = max(0, (event.date - state.as_of_date).days)

            if current_balance < minimum_cash_buffer:
                if days_to_buffer_breach is None:
                    days_to_buffer_breach = days_diff
                shortfalls.append(
                    BreachEvent(
                        breach_date=event.date,
                        projected_balance=current_balance,
                        shortfall_amount=minimum_cash_buffer - current_balance,
                        triggering_event=event,
                        is_zero_breach=False,
                    )
                )

            if current_balance < 0:
                if days_to_zero is None:
                    days_to_zero = days_diff
                shortfalls.append(
                    BreachEvent(
                        breach_date=event.date,
                        projected_balance=current_balance,
                        shortfall_amount=abs(current_balance),
                        triggering_event=event,
                        is_zero_breach=True,
                    )
                )

        min_balance = min(projected_balances.values()) if projected_balances else state.current_cash

        return CashFlowProjection(
            as_of_date=state.as_of_date,
            starting_balance=state.current_cash,
            minimum_cash_buffer=minimum_cash_buffer,
            receivable_mode=receivable_mode,
            forecast_mode=forecast_mode,
            events=events,
            projected_balances=projected_balances,
            days_to_zero=days_to_zero,
            days_to_buffer_breach=days_to_buffer_breach,
            shortfalls=shortfalls,
            minimum_projected_balance=min_balance,
        )
