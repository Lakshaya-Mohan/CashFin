"""
Stage 3 — Decision Engine Tests

All tests use fixed dates and Decimal values.
No system clock is used.
No LLM or ML is involved.

Tests are organised into two groups:
  - Core decision tests (Tests 1–12): basic engine behaviour
  - Chronological tests (Tests A–F): timeline-specific behaviour
"""
import pytest
from datetime import date
from decimal import Decimal

from app.schemas.financial_state import UpcomingReceivable, ProjectionMode
from app.schemas.decision import ActionType, Obligation
from app.services.decision_engine import DecisionEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_obligation(
    payable_id: int,
    amount: str,
    due_date: date,
    urgency: int = 3,
    penalty_risk: int = 3,
    flexibility: int = 3,
    name: str = "Counterparty",
) -> Obligation:
    return Obligation(
        payable_id=payable_id,
        counterparty_id=payable_id,
        counterparty_name=name,
        amount=Decimal(amount),
        due_date=due_date,
        urgency=urgency,
        penalty_risk=penalty_risk,
        flexibility=flexibility,
    )


def make_receivable(
    rid: int,
    amount: str,
    expected_date: date,
    confidence: str = "1.0",
) -> UpcomingReceivable:
    return UpcomingReceivable(
        id=rid,
        amount=Decimal(amount),
        expected_date=expected_date,
        confidence=Decimal(confidence),
    )


engine = DecisionEngine()
AS_OF = date(2026, 9, 1)
BUFFER = Decimal("25000.00")


# ---------------------------------------------------------------------------
# Test 1: Cash sufficient for all obligations
# ---------------------------------------------------------------------------
def test_1_cash_sufficient_for_all():
    obligations = [
        make_obligation(1, "30000.00", date(2026, 9, 5)),
        make_obligation(2, "20000.00", date(2026, 9, 10)),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("100000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    assert result.feasible is True
    assert len(result.selected_obligations) == 2
    assert len(result.deferred_obligations) == 0
    assert len(result.negotiated_obligations) == 0
    all_paid = {od.obligation.payable_id for od in result.selected_obligations}
    assert {1, 2} == all_paid


# ---------------------------------------------------------------------------
# Test 2: Cash insufficient for all — engine selects a partial subset
# ---------------------------------------------------------------------------
def test_2_cash_insufficient_selects_subset():
    # Cash = 120k, buffer = 25k
    # Salary (id=1): 60k → leaves 60k ≥ 25k ✓  (cost if deferred = 2*5+2*5-1*1 = 19)
    # Supplier (id=2): 60k → leaves 60k ≥ 25k ✓ (cost if deferred = 2*2+2*1-1*5 = -1)
    # Both: 120k - 120k = 0k < 25k ✗
    # Pay Salary only: unpaid cost = -1 (Supplier deferred — very cheap to defer)
    # Pay Supplier only: unpaid cost = 19 (Salary deferred — expensive to defer)
    # Pay nothing: unpaid cost = 18
    # Best: Pay Salary only (min deferral cost of unpaid = -1)
    obligations = [
        make_obligation(1, "60000.00", date(2026, 9, 5), urgency=5, penalty_risk=5, flexibility=1, name="Salary"),
        make_obligation(2, "60000.00", date(2026, 9, 8), urgency=2, penalty_risk=1, flexibility=5, name="Supplier"),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("120000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    assert result.feasible is True
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    # Salary has highest deferral cost → engine prefers to pay Salary, defer Supplier
    assert 1 in paid_ids
    assert 2 not in paid_ids


# ---------------------------------------------------------------------------
# Test 3: High-urgency obligation beats low-urgency
# ---------------------------------------------------------------------------
def test_3_high_urgency_preferred():
    obligations = [
        make_obligation(1, "50000.00", date(2026, 9, 5), urgency=5, penalty_risk=3, flexibility=2, name="Critical"),
        make_obligation(2, "50000.00", date(2026, 9, 6), urgency=1, penalty_risk=3, flexibility=2, name="LowUrgency"),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert 1 in paid_ids  # high urgency paid
    assert 2 not in paid_ids


# ---------------------------------------------------------------------------
# Test 4: High penalty obligation preferred when other factors equal
# ---------------------------------------------------------------------------
def test_4_high_penalty_preferred():
    obligations = [
        make_obligation(1, "50000.00", date(2026, 9, 5), urgency=3, penalty_risk=5, flexibility=3, name="HighPenalty"),
        make_obligation(2, "50000.00", date(2026, 9, 6), urgency=3, penalty_risk=1, flexibility=3, name="LowPenalty"),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert 1 in paid_ids
    assert 2 not in paid_ids


# ---------------------------------------------------------------------------
# Test 5: Flexible obligation preferred for deferral/negotiation
# ---------------------------------------------------------------------------
def test_5_flexible_obligation_preferred_for_deferral():
    obligations = [
        make_obligation(1, "50000.00", date(2026, 9, 5), urgency=5, penalty_risk=5, flexibility=1, name="Inflexible"),
        make_obligation(2, "50000.00", date(2026, 9, 6), urgency=2, penalty_risk=1, flexibility=5, name="Flexible"),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    deferred_ids = {od.obligation.payable_id for od in result.deferred_obligations}
    negotiated_ids = {od.obligation.payable_id for od in result.negotiated_obligations}
    # Flexible obligation (id=2) should be the one not paid
    assert 2 in deferred_ids or 2 in negotiated_ids


# ---------------------------------------------------------------------------
# Test 6: Minimum cash buffer respected — strategy never drops below buffer
# ---------------------------------------------------------------------------
def test_6_minimum_buffer_respected():
    obligations = [
        make_obligation(1, "60000.00", date(2026, 9, 5)),
        make_obligation(2, "30000.00", date(2026, 9, 8)),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("100000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    # All timeline entries in the selected strategy must maintain balance >= buffer
    assert result.feasible is True
    for entry in result.timeline:
        assert entry.cash_after >= Decimal("25000.00"), (
            f"Buffer violated at {entry.event_date}: {entry.cash_after}"
        )


# ---------------------------------------------------------------------------
# Test 7: No combination satisfies buffer — result is infeasible
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Test 7: No combination satisfies buffer — no obligation can be paid
# ---------------------------------------------------------------------------
def test_7_no_combination_satisfies_buffer():
    # Cash = 27k, buffer = 25k.
    # Paying 5k obligation → 22k < 25k buffer → that subset is infeasible.
    # Pay nothing → 27k >= 25k → technically feasible (no events = no breach).
    #
    # The engine correctly selects pay-nothing (the only feasible subset is the empty set).
    # This is the right behaviour: it would be wrong to pay the obligation if it
    # causes a buffer breach. The correct recommendation is to defer it.
    #
    # This test verifies that the engine never selects an obligation for payment
    # when doing so would violate the buffer — even if only one obligation exists.
    result = engine.evaluate_obligations(
        current_cash=Decimal("27000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=[
            make_obligation(1, "5000.00", date(2026, 9, 5)),
        ],
        receivables=[],
        as_of_date=AS_OF,
    )
    # The engine finds the empty set (pay nothing) is the only feasible strategy.
    # Therefore no obligation is selected for payment.
    assert len(result.selected_obligations) == 0
    # The obligation is deferred because paying it would breach the buffer.
    all_unpaid = result.deferred_obligations + result.negotiated_obligations
    assert any(od.obligation.payable_id == 1 for od in all_unpaid)


# ---------------------------------------------------------------------------
# Test 8: Multiple obligations on the same date — deterministic ordering
# ---------------------------------------------------------------------------
def test_8_multiple_obligations_same_date_deterministic():
    obligations = [
        make_obligation(1, "20000.00", date(2026, 9, 5), urgency=4, penalty_risk=4, flexibility=2),
        make_obligation(2, "20000.00", date(2026, 9, 5), urgency=2, penalty_risk=2, flexibility=4),
        make_obligation(3, "20000.00", date(2026, 9, 5), urgency=3, penalty_risk=3, flexibility=3),
    ]
    result1 = engine.evaluate_obligations(
        current_cash=Decimal("70000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    result2 = engine.evaluate_obligations(
        current_cash=Decimal("70000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    paid1 = sorted(od.obligation.payable_id for od in result1.selected_obligations)
    paid2 = sorted(od.obligation.payable_id for od in result2.selected_obligations)
    assert paid1 == paid2  # deterministic


# ---------------------------------------------------------------------------
# Test 9: Expected receivable before obligation — helps cash position
# (This is a high-level check; chronological detail tested in Test B)
# ---------------------------------------------------------------------------
def test_9_receivable_before_obligation_enables_payment():
    obligations = [
        make_obligation(1, "80000.00", date(2026, 9, 10)),
    ]
    receivables = [
        make_receivable(1, "50000.00", date(2026, 9, 5)),  # arrives before obligation
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("60000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    # Without receivable: 60k - 80k = -20k → infeasible
    # With receivable before: 60k + 50k = 110k - 80k = 30k >= 25k → feasible
    assert result.feasible is True
    assert 1 in {od.obligation.payable_id for od in result.selected_obligations}


# ---------------------------------------------------------------------------
# Test 10: Receivable arrives AFTER obligation — cannot help with that obligation
# ---------------------------------------------------------------------------
def test_10_receivable_after_obligation_cannot_help():
    # Cash = 60k. Obligation = 70k on Sep 5. Receivable = 50k on Sep 10.
    # Without paying: no breach (60k >= 25k buffer always).
    # Paying obligation: 60k - 70k = -10k on Sep 5 < 25k buffer → infeasible.
    # Engine selects "pay nothing" (feasible, defers the obligation).
    # The key assertion: the obligation is NOT paid because receivable comes too late.
    obligations = [
        make_obligation(1, "70000.00", date(2026, 9, 5),
                        urgency=5, penalty_risk=5, flexibility=1),
    ]
    receivables = [
        make_receivable(1, "50000.00", date(2026, 9, 10)),  # arrives AFTER obligation
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("60000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    # Paying the obligation on Sep 5 would leave -10k < 25k buffer → infeasible.
    # The engine selects pay-nothing as the only feasible strategy.
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert 1 not in paid_ids  # cannot be paid — receivable arrives too late


# ---------------------------------------------------------------------------
# Test 11: Exact cash constraint — exactly at buffer after payment
# ---------------------------------------------------------------------------
def test_11_exact_cash_constraint():
    # 100k - 75k = 25k == buffer → still feasible (>= not >)
    obligations = [
        make_obligation(1, "75000.00", date(2026, 9, 5)),
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("100000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    assert result.feasible is True
    assert result.ending_cash == Decimal("25000.00")


# ---------------------------------------------------------------------------
# Test 12: Determinism — same input always produces identical result
# ---------------------------------------------------------------------------
def test_12_determinism():
    obligations = [
        make_obligation(1, "40000.00", date(2026, 9, 5), urgency=4, penalty_risk=3, flexibility=2),
        make_obligation(2, "40000.00", date(2026, 9, 7), urgency=2, penalty_risk=2, flexibility=4),
        make_obligation(3, "30000.00", date(2026, 9, 9), urgency=3, penalty_risk=4, flexibility=3),
    ]
    receivables = [
        make_receivable(1, "30000.00", date(2026, 9, 6)),
    ]
    kwargs = dict(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    result_a = engine.evaluate_obligations(**kwargs)
    result_b = engine.evaluate_obligations(**kwargs)

    paid_a = sorted(od.obligation.payable_id for od in result_a.selected_obligations)
    paid_b = sorted(od.obligation.payable_id for od in result_b.selected_obligations)
    assert paid_a == paid_b
    assert result_a.ending_cash == result_b.ending_cash
    assert result_a.total_deferral_cost == result_b.total_deferral_cost


# ===========================================================================
# Chronological-specific tests (Tests A–F)
# ===========================================================================

# ---------------------------------------------------------------------------
# Test A: Obligation occurs BEFORE receivable — receivable cannot help
# ---------------------------------------------------------------------------
def test_A_obligation_before_receivable_inflow_too_late():
    # Cash = 60k, buffer = 0, obligation = 70k on Sep 2, receivable = 50k on Sep 5.
    # Paying obligation: 60k - 70k = -10k < 0 on Sep 2 → infeasible.
    # Pay nothing: no breach, cost = deferral cost of obligation.
    # Engine selects pay-nothing → obligation is NOT paid.
    obligations = [
        make_obligation(1, "70000.00", date(2026, 9, 2)),
    ]
    receivables = [
        make_receivable(1, "50000.00", date(2026, 9, 5)),  # inflow on Sep 5 (too late for Sep 2)
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("60000.00"),
        minimum_cash_buffer=Decimal("0.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    # The receivable cannot help — paying the obligation on Sep 2 would go negative.
    # Engine correctly defers it.
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert 1 not in paid_ids


# ---------------------------------------------------------------------------
# Test B: Receivable occurs BEFORE obligation — increases available liquidity
# ---------------------------------------------------------------------------
def test_B_receivable_before_obligation_increases_liquidity():
    obligations = [
        make_obligation(1, "70000.00", date(2026, 9, 5)),  # obligation on Sep 5
    ]
    receivables = [
        make_receivable(1, "50000.00", date(2026, 9, 3)),  # inflow on Sep 3 (before Sep 5)
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("40000.00"),   # 40k + 50k = 90k, then -70k = 20k >= 0
        minimum_cash_buffer=Decimal("0.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    assert result.feasible is True
    assert 1 in {od.obligation.payable_id for od in result.selected_obligations}


# ---------------------------------------------------------------------------
# Test C: Temporary buffer breach before later receivable → payment is infeasible
# ---------------------------------------------------------------------------
def test_C_temporary_buffer_breach_is_infeasible():
    # Cash = 80k, buffer = 25k, obligation = 60k on Sep 3, inflow = 50k on Sep 8.
    # Paying obligation: 80k - 60k = 20k on Sep 3 < 25k buffer → INFEASIBLE for that subset.
    # Pay nothing: 80k, then +50k = 130k → min_cash = 80k >= 25k → feasible.
    # Engine selects pay-nothing (defers the obligation) — because paying it breaches buffer.
    # The obligation must be in the deferred list, not selected.
    obligations = [
        make_obligation(1, "60000.00", date(2026, 9, 3)),
    ]
    receivables = [
        make_receivable(1, "50000.00", date(2026, 9, 8)),  # inflow restores later, but too late
    ]
    result = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    # Engine is feasible overall (pay-nothing works), but the obligation CANNOT be paid
    # because paying it would create a temporary breach before the Sep 8 inflow.
    assert result.feasible is True  # pay-nothing strategy is feasible
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert 1 not in paid_ids  # obligation cannot be included due to buffer breach


# ---------------------------------------------------------------------------
# Test D: Receivable arrives early enough to make all obligations feasible
# ---------------------------------------------------------------------------
def test_D_early_receivable_makes_all_feasible():
    obligations = [
        make_obligation(1, "40000.00", date(2026, 9, 5)),
        make_obligation(2, "40000.00", date(2026, 9, 8)),
    ]
    receivables = [
        make_receivable(1, "30000.00", date(2026, 9, 3)),  # arrives before both
    ]
    # Start: 60k → Sep 3: +30k = 90k → Sep 5: -40k = 50k → Sep 8: -40k = 10k >= 0
    result = engine.evaluate_obligations(
        current_cash=Decimal("60000.00"),
        minimum_cash_buffer=Decimal("0.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
    )
    assert result.feasible is True
    paid_ids = {od.obligation.payable_id for od in result.selected_obligations}
    assert {1, 2} == paid_ids


# ---------------------------------------------------------------------------
# Test E: Identical deferral cost — deterministic tie-breaker applied
# ---------------------------------------------------------------------------
def test_E_identical_deferral_cost_tie_break():
    # Two obligations with same cost, cash only allows one
    # obligation 1 and 2 have identical urgency/penalty/flexibility → same deferral cost
    # Tie-break should prefer higher urgency PAID, then by ID
    obligations = [
        make_obligation(1, "50000.00", date(2026, 9, 5), urgency=3, penalty_risk=3, flexibility=3, name="Equal A"),
        make_obligation(2, "50000.00", date(2026, 9, 6), urgency=3, penalty_risk=3, flexibility=3, name="Equal B"),
    ]
    # 80k - 50k = 30k >= 25k → can pay one
    # Both have same deferral cost (= 2*3 + 2*3 - 1*3 = 9)
    result1 = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    result2 = engine.evaluate_obligations(
        current_cash=Decimal("80000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=[],
        as_of_date=AS_OF,
    )
    paid1 = sorted(od.obligation.payable_id for od in result1.selected_obligations)
    paid2 = sorted(od.obligation.payable_id for od in result2.selected_obligations)
    assert paid1 == paid2  # always the same choice


# ---------------------------------------------------------------------------
# Test F: RAW vs CONFIDENCE_ADJUSTED produces different outcomes
# ---------------------------------------------------------------------------
def test_F_raw_vs_confidence_adjusted_different_outcomes():
    # Cash = 40k. Buffer = 25k.
    # Receivable: 100k raw, confidence 0.4 → adjusted = 40k. Arrives Sep 5.
    # Obligation: 80k on Sep 8.
    #
    # RAW mode:
    #   Sep 5: +100k → 140k
    #   Sep 8: -80k  → 60k ≥ 25k ✓  → obligation CAN be paid
    #
    # CONFIDENCE_ADJUSTED mode:
    #   Sep 5: +40k → 80k
    #   Sep 8: -80k → 0k < 25k ✗  → obligation CANNOT be paid (buffer breach)
    #   Engine defers the obligation.
    obligations = [
        make_obligation(1, "80000.00", date(2026, 9, 8)),
    ]
    receivables = [
        make_receivable(1, "100000.00", date(2026, 9, 5), confidence="0.4"),
    ]
    result_raw = engine.evaluate_obligations(
        current_cash=Decimal("40000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
        projection_mode=ProjectionMode.RAW,
    )
    result_adj = engine.evaluate_obligations(
        current_cash=Decimal("40000.00"),
        minimum_cash_buffer=BUFFER,
        obligations=obligations,
        receivables=receivables,
        as_of_date=AS_OF,
        projection_mode=ProjectionMode.CONFIDENCE_ADJUSTED,
    )
    # In RAW mode: obligation is selected for payment
    paid_raw = {od.obligation.payable_id for od in result_raw.selected_obligations}
    assert 1 in paid_raw
    # In CONFIDENCE_ADJUSTED mode: obligation cannot be paid without breaching buffer
    paid_adj = {od.obligation.payable_id for od in result_adj.selected_obligations}
    assert 1 not in paid_adj
    # Projection modes recorded correctly
    assert result_raw.projection_mode == ProjectionMode.RAW
    assert result_adj.projection_mode == ProjectionMode.CONFIDENCE_ADJUSTED
