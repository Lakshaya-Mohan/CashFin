"""
CashFin Decision Engine — Stage 3

PURPOSE
-------
Given the current cash position, minimum cash buffer, a list of pending obligations,
and expected inflows, determine the optimal payment strategy for the company.

ALGORITHM OVERVIEW
------------------
1. Enumerate every subset of obligations (exhaustive for MVP; feasible for small counts).
2. For each subset selected to pay:
   a. Build the full chronological event timeline (paid outflows + inflows).
   b. Simulate the cash balance step by step through time.
   c. Verify the cash balance >= minimum_cash_buffer at EVERY point (not just at the end).
   d. If feasible, compute the total deferral cost for unpaid obligations.
3. Select the feasible subset with the lowest total deferral cost.
4. Apply deterministic tie-breaking when costs are equal.
5. After the optimal strategy is chosen, classify unpaid obligations as DEFER or NEGOTIATE.

COST MODEL
----------
cost_of_deferral(obligation) =
    urgency_weight  * urgency
  + penalty_weight  * penalty_risk
  - flexibility_weight * flexibility

This is a HEURISTIC business scoring model, not a mathematically proven financial loss metric.
The weights represent relative business consequence:
  - urgency_weight=2.0   : Time criticality of the payment
  - penalty_weight=2.0   : Financial/legal consequence of non-payment
  - flexibility_weight=1.0: Ability to reschedule (negative contribution — easier to defer)

Weights are configurable at DecisionEngine construction time.

CLASSIFICATION RULES
--------------------
After the optimal pay/defer split is determined, unpaid obligations are classified:

  NEGOTIATE if: (flexibility - penalty_risk) >= 2 AND urgency <= 3
    → Counterparty relationship is likely to accept rescheduled terms.
    → Does NOT imply the negotiation will succeed.

  DEFER otherwise:
    → Lower flexibility or higher urgency/penalty risk means deferral carries greater risk.
    → Requires immediate internal attention.

TIE-BREAKING
------------
When two strategies share the same total deferral cost, prefer by:
  1. Higher minimum projected cash (more financial headroom)
  2. Fewer deferred obligations
  3. Higher total urgency of PAID obligations (we protected the most critical)
  4. Lexicographically smaller sorted tuple of paid obligation IDs (stable determinism)
"""

from datetime import date
from decimal import Decimal
from itertools import combinations
from typing import List, Optional, Tuple, Dict

from app.schemas.financial_state import UpcomingReceivable, ReceivableMode
from app.schemas.decision import (
    Obligation, ObligationDecision, ActionType, DecisionFactor,
    DecisionResult, TimelineEntry
)

# Default configurable weights — see module docstring for explanation
DEFAULT_WEIGHTS: Dict[str, float] = {
    'urgency': 2.0,
    'penalty': 2.0,
    'flexibility': 1.0,
}

# Negotiation classification thresholds — see module docstring
NEGOTIATE_MIN_SCORE = 2     # flexibility - penalty_risk must be >= this
NEGOTIATE_MAX_URGENCY = 3   # urgency must be <= this to recommend negotiation


class DecisionEngine:
    def __init__(self, weights: Dict[str, float] = None):
        """
        :param weights: Override default urgency/penalty/flexibility weights.
                        Dict keys: 'urgency', 'penalty', 'flexibility'.
        """
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def evaluate_obligations(
        self,
        current_cash: Decimal,
        minimum_cash_buffer: Decimal,
        obligations: List[Obligation],
        receivables: List[UpcomingReceivable],
        as_of_date: date,
        receivable_mode: ReceivableMode = ReceivableMode.RAW,
    ) -> DecisionResult:
        """
        Entry point for the Decision Engine.

        Evaluates all feasible payment strategies and returns the structured
        DecisionResult for the optimal strategy.

        All output is a RECOMMENDATION. No payment has been executed.
        """
        total_obligations = sum(o.amount for o in obligations)
        total_expected_inflows = sum(
            r.amount if receivable_mode == ReceivableMode.RAW else r.amount * r.confidence
            for r in receivables
        )

        # Pre-compute deferral costs — used repeatedly during enumeration
        deferral_costs: Dict[int, float] = {
            o.payable_id: self._compute_deferral_cost(o) for o in obligations
        }

        best_scenario: Optional[Tuple] = None
        best_key = None

        # Enumerate all 2^n subsets, largest first (so full-payment is tested early)
        n = len(obligations)
        for size in range(n, -1, -1):
            for combo in combinations(obligations, size):
                paid_set = list(combo)
                paid_ids = {o.payable_id for o in paid_set}
                unpaid_set = [o for o in obligations if o.payable_id not in paid_ids]

                is_feasible, ending_cash, min_cash, date_of_min, timeline, _ = \
                    self._simulate_timeline(
                        current_cash, paid_set, receivables,
                        minimum_cash_buffer, receivable_mode
                    )

                if not is_feasible:
                    continue

                unpaid_cost = sum(deferral_costs[o.payable_id] for o in unpaid_set)
                deferred_count = len(unpaid_set)

                tie_key = self._tie_break_key(
                    unpaid_cost, paid_set, min_cash, deferred_count
                )

                if best_key is None or tie_key < best_key:
                    best_scenario = (
                        unpaid_cost, paid_set, unpaid_set,
                        min_cash, date_of_min, ending_cash, timeline
                    )
                    best_key = tie_key

        if best_scenario is None:
            return self._build_infeasible_result(
                current_cash, minimum_cash_buffer, obligations, receivables,
                as_of_date, receivable_mode, total_obligations,
                total_expected_inflows, deferral_costs
            )

        unpaid_cost, paid_set, unpaid_set, min_cash, date_of_min, ending_cash, timeline = best_scenario

        selected = [
            ObligationDecision(
                obligation=o,
                action=ActionType.PAY,
                deferral_cost=None,
                decision_factors=self._build_decision_factors(o),
                reasoning=(
                    f"Recommended for payment. Urgency={o.urgency}/5, "
                    f"Penalty risk={o.penalty_risk}/5. "
                    f"Deferral cost would have been {deferral_costs[o.payable_id]:.2f}."
                )
            )
            for o in paid_set
        ]

        deferred, negotiated = [], []
        for o in unpaid_set:
            action = self._classify_unpaid(o)
            od = ObligationDecision(
                obligation=o,
                action=action,
                deferral_cost=deferral_costs[o.payable_id],
                decision_factors=self._build_decision_factors(o),
                reasoning=self._build_reasoning(o, action)
            )
            if action == ActionType.NEGOTIATE:
                negotiated.append(od)
            else:
                deferred.append(od)

        shortfall = (minimum_cash_buffer - min_cash) if min_cash < minimum_cash_buffer else None

        return DecisionResult(
            feasible=True,
            as_of_date=as_of_date,
            receivable_mode=receivable_mode,
            initial_cash=current_cash,
            minimum_cash_buffer=minimum_cash_buffer,
            total_obligations=total_obligations,
            total_expected_inflows=total_expected_inflows,
            selected_obligations=selected,
            deferred_obligations=deferred,
            negotiated_obligations=negotiated,
            ending_cash=ending_cash,
            minimum_projected_cash=min_cash,
            date_of_minimum_projected_cash=date_of_min,
            projected_shortfall=shortfall,
            total_deferral_cost=unpaid_cost,
            timeline=timeline,
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _compute_deferral_cost(self, obligation: Obligation) -> float:
        """
        Heuristic cost of deferring an obligation.
        Higher = worse to defer (higher urgency/penalty, lower flexibility).
        Lower = better candidate for deferral (lower urgency/penalty, higher flexibility).
        """
        return (
            self.weights['urgency']     * obligation.urgency
            + self.weights['penalty']   * obligation.penalty_risk
            - self.weights['flexibility'] * obligation.flexibility
        )

    def _build_decision_factors(self, obligation: Obligation) -> List[DecisionFactor]:
        return [
            DecisionFactor(
                factor_name="Urgency",
                raw_value=obligation.urgency,
                weight=self.weights['urgency'],
                contribution=self.weights['urgency'] * obligation.urgency,
            ),
            DecisionFactor(
                factor_name="Penalty Risk",
                raw_value=obligation.penalty_risk,
                weight=self.weights['penalty'],
                contribution=self.weights['penalty'] * obligation.penalty_risk,
            ),
            DecisionFactor(
                factor_name="Flexibility (inverse)",
                raw_value=obligation.flexibility,
                weight=-self.weights['flexibility'],
                contribution=-self.weights['flexibility'] * obligation.flexibility,
            ),
        ]

    def _classify_unpaid(self, obligation: Obligation) -> ActionType:
        """
        Classify an unpaid obligation as DEFER or NEGOTIATE.

        NEGOTIATE if:
          - (flexibility - penalty_risk) >= NEGOTIATE_MIN_SCORE (= 2)
          - AND urgency <= NEGOTIATE_MAX_URGENCY (= 3)

        This reflects that negotiation is only viable when:
          - the counterparty has historically shown flexibility (high flexibility score)
          - the payment is not a critical legal/contractual obligation (low penalty risk)
          - the obligation is not immediately urgent (low urgency)

        IMPORTANT: A NEGOTIATE recommendation is a suggested course of action only.
        It does NOT imply the negotiation will succeed or has been initiated.
        """
        negotiate_score = obligation.flexibility - obligation.penalty_risk
        if negotiate_score >= NEGOTIATE_MIN_SCORE and obligation.urgency <= NEGOTIATE_MAX_URGENCY:
            return ActionType.NEGOTIATE
        return ActionType.DEFER

    def _build_reasoning(self, obligation: Obligation, action: ActionType) -> str:
        if action == ActionType.NEGOTIATE:
            return (
                f"Suggested for negotiation. Flexibility={obligation.flexibility}/5, "
                f"Penalty risk={obligation.penalty_risk}/5 (negotiate score="
                f"{obligation.flexibility - obligation.penalty_risk}), "
                f"Urgency={obligation.urgency}/5. "
                f"The counterparty may accept rescheduled terms. "
                f"This is a recommendation only — no negotiation has been initiated."
            )
        return (
            f"Suggested deferral. Urgency={obligation.urgency}/5, "
            f"Penalty risk={obligation.penalty_risk}/5, "
            f"Flexibility={obligation.flexibility}/5. "
            f"Low flexibility or high urgency/penalty risk means deferral carries significant risk. "
            f"This obligation requires prompt internal attention."
        )

    def _simulate_timeline(
        self,
        current_cash: Decimal,
        paid_obligations: List[Obligation],
        receivables: List[UpcomingReceivable],
        minimum_cash_buffer: Decimal,
        receivable_mode: ReceivableMode,
    ) -> Tuple[bool, Decimal, Decimal, Optional[date], List[TimelineEntry], Optional[date]]:
        """
        Simulate cash balance through time for a proposed payment strategy.

        Events are sorted chronologically. On the same date, inflows are
        processed before outflows to give the maximum available cash advantage
        (deterministic ordering: date → inflow_first → source_id).

        The minimum cash buffer is checked at EVERY event, not just at the end.
        A strategy that temporarily drops below the buffer is INFEASIBLE,
        even if a later receivable would restore the balance.

        Returns:
            (is_feasible, ending_cash, min_cash_seen, date_of_min, timeline, first_breach_date)
        """
        # Build flat event list: (date, is_outflow, amount, description, source_id)
        events = []
        for o in paid_obligations:
            events.append((o.due_date, True, o.amount,
                           f"PAY: {o.description or o.counterparty_name}", o.payable_id))

        for r in receivables:
            amount = r.amount if receivable_mode == ReceivableMode.RAW else r.amount * r.confidence
            events.append((r.expected_date, False, amount,
                           f"INFLOW: {r.description or 'Receivable'}", r.id))

        # Deterministic sort: date, inflows first (is_outflow=False < True), then source_id
        events.sort(key=lambda e: (e[0], e[1], e[4]))

        timeline: List[TimelineEntry] = []
        balance = current_cash
        min_cash = current_cash
        date_of_min: Optional[date] = None
        first_breach_date: Optional[date] = None

        for event_date, is_outflow, amount, description, _ in events:
            cash_before = balance
            balance = balance - amount if is_outflow else balance + amount

            timeline.append(TimelineEntry(
                event_date=event_date,
                description=description,
                event_type="OUTFLOW" if is_outflow else "INFLOW",
                amount=amount,
                cash_before=cash_before,
                cash_after=balance,
            ))

            if balance < min_cash:
                min_cash = balance
                date_of_min = event_date

            if balance < minimum_cash_buffer and first_breach_date is None:
                first_breach_date = event_date

        is_feasible = first_breach_date is None
        return is_feasible, balance, min_cash, date_of_min, timeline, first_breach_date

    def _tie_break_key(
        self,
        deferral_cost: float,
        paid_set: List[Obligation],
        min_cash: Decimal,
        deferred_count: int,
    ) -> tuple:
        """
        Deterministic tie-breaking tuple (lower = better scenario).

        Priority:
          1. Lowest deferral cost (primary objective)
          2. Highest minimum projected cash (negate for ascending sort)
          3. Fewest deferred obligations
          4. Highest total urgency of PAID obligations (protected the most critical)
          5. Lexicographically smallest sorted tuple of paid IDs (stable)
        """
        sum_urgency_paid = sum(o.urgency for o in paid_set)
        paid_ids = tuple(sorted(o.payable_id for o in paid_set))
        return (
            deferral_cost,
            -float(min_cash),    # negate: higher min_cash is better
            deferred_count,
            -sum_urgency_paid,   # negate: higher urgency paid is better
            paid_ids,
        )

    def _build_infeasible_result(
        self,
        current_cash: Decimal,
        minimum_cash_buffer: Decimal,
        obligations: List[Obligation],
        receivables: List[UpcomingReceivable],
        as_of_date: date,
        receivable_mode: ReceivableMode,
        total_obligations: Decimal,
        total_expected_inflows: Decimal,
        deferral_costs: Dict[int, float],
    ) -> DecisionResult:
        """
        No feasible strategy exists. Run the pay-nothing simulation to
        establish the baseline timeline and identify the breach point.
        """
        _, ending_cash, min_cash, date_of_min, timeline, _ = self._simulate_timeline(
            current_cash, [], receivables, minimum_cash_buffer, receivable_mode
        )

        shortfall = (minimum_cash_buffer - min_cash) if min_cash < minimum_cash_buffer else Decimal('0.00')
        all_deferred = []
        for o in obligations:
            action = self._classify_unpaid(o)
            od = ObligationDecision(
                obligation=o,
                action=action,
                deferral_cost=deferral_costs[o.payable_id],
                decision_factors=self._build_decision_factors(o),
                reasoning=(
                    "No feasible payment strategy exists that satisfies the minimum cash buffer "
                    "constraint. All obligations are recommended for deferral or negotiation pending "
                    "liquidity review. This is a recommendation only."
                )
            )
            if action == ActionType.NEGOTIATE:
                all_deferred  # keep in deferred for infeasible
            all_deferred.append(od)

        return DecisionResult(
            feasible=False,
            as_of_date=as_of_date,
            receivable_mode=receivable_mode,
            initial_cash=current_cash,
            minimum_cash_buffer=minimum_cash_buffer,
            total_obligations=total_obligations,
            total_expected_inflows=total_expected_inflows,
            selected_obligations=[],
            deferred_obligations=all_deferred,
            negotiated_obligations=[],
            ending_cash=ending_cash,
            minimum_projected_cash=min_cash,
            date_of_minimum_projected_cash=date_of_min,
            projected_shortfall=shortfall,
            total_deferral_cost=sum(deferral_costs.values()),
            timeline=timeline,
        )
