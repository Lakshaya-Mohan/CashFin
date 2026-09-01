"""
CashFin — Stage 3 Stress-Test Demo

Scenario (chronological liquidity conflict):
  Current cash:   Rs. 100,000
  Minimum buffer: Rs.  25,000

  Sep 2: Salary        Rs. 50,000  Urgency=5 Penalty=5 Flexibility=1
  Sep 3: Supplier A    Rs. 35,000  Urgency=3 Penalty=2 Flexibility=4
  Sep 5: Customer REC  Rs. 60,000  Confidence=0.9
  Sep 6: Rent          Rs. 30,000  Urgency=5 Penalty=4 Flexibility=1

The engine must reason about actual dates (not just total cash vs total obligations).
Key insight: paying Salary + Supplier A causes a buffer breach on Sep 3
before the receivable arrives on Sep 5.
"""
import sys
import io

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from datetime import date
from decimal import Decimal

from app.schemas.financial_state import UpcomingReceivable, ReceivableMode
from app.schemas.decision import Obligation, ActionType
from app.services.decision_engine import DecisionEngine


def run_stress_test():
    print("=" * 60)
    print("CashFin — Stage 3 Chronological Stress-Test Demo")
    print("=" * 60)

    engine = DecisionEngine()

    obligations = [
        Obligation(
            payable_id=1,
            counterparty_id=1,
            counterparty_name="Employee",
            amount=Decimal("50000.00"),
            due_date=date(2026, 9, 2),
            urgency=5,
            penalty_risk=5,
            flexibility=1,
            description="Salary",
        ),
        Obligation(
            payable_id=2,
            counterparty_id=2,
            counterparty_name="ABC Hardware",
            amount=Decimal("35000.00"),
            due_date=date(2026, 9, 3),
            urgency=3,
            penalty_risk=2,
            flexibility=4,
            description="Supplier A",
        ),
        Obligation(
            payable_id=3,
            counterparty_id=3,
            counterparty_name="Office Landlord",
            amount=Decimal("30000.00"),
            due_date=date(2026, 9, 6),
            urgency=5,
            penalty_risk=4,
            flexibility=1,
            description="Rent",
        ),
    ]

    receivables = [
        UpcomingReceivable(
            id=1,
            amount=Decimal("60000.00"),
            expected_date=date(2026, 9, 5),
            confidence=Decimal("0.9"),
            description="Customer Payment",
        )
    ]

    result = engine.evaluate_obligations(
        current_cash=Decimal("100000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=date(2026, 9, 1),
        projection_mode=ReceivableMode.RAW,
    )

    print(f"\nProjection Mode : {result.projection_mode}")
    print(f"Feasible        : {result.feasible}")
    print(f"Initial Cash    : Rs. {result.initial_cash:>12,.2f}")
    print(f"Minimum Buffer  : Rs. {result.minimum_cash_buffer:>12,.2f}")
    print(f"Total Obligations: Rs. {result.total_obligations:>11,.2f}")
    print(f"Total Inflows   : Rs. {result.total_expected_inflows:>12,.2f}")

    print("\n--- Recommended Payments (PAY) ---")
    if result.selected_obligations:
        for od in result.selected_obligations:
            o = od.obligation
            print(f"  [{od.action}] {o.description or o.counterparty_name:20s}  "
                  f"Rs. {o.amount:>10,.2f}  due {o.due_date}")
    else:
        print("  (none)")

    print("\n--- Deferred Obligations (DEFER) ---")
    if result.deferred_obligations:
        for od in result.deferred_obligations:
            o = od.obligation
            print(f"  [{od.action}] {o.description or o.counterparty_name:20s}  "
                  f"Rs. {o.amount:>10,.2f}  cost={od.deferral_cost:.2f}")
            print(f"           {od.reasoning}")
    else:
        print("  (none)")

    print("\n--- Negotiation Candidates (NEGOTIATE) ---")
    if result.negotiated_obligations:
        for od in result.negotiated_obligations:
            o = od.obligation
            print(f"  [{od.action}] {o.description or o.counterparty_name:20s}  "
                  f"Rs. {o.amount:>10,.2f}  cost={od.deferral_cost:.2f}")
            print(f"           {od.reasoning}")
    else:
        print("  (none)")

    print("\n--- Chronological Cash Timeline (Selected Strategy) ---")
    print(f"  {'Date':<12} {'Event':<30} {'Type':<8} {'Amount':>12}  {'Before':>12}  {'After':>12}")
    print(f"  {'-'*12} {'-'*30} {'-'*8} {'-'*12}  {'-'*12}  {'-'*12}")
    bal = result.initial_cash
    print(f"  {'(start)':12} {'Starting balance':30} {'':8} {'':>12}  {'':>12}  Rs. {bal:>10,.2f}")
    for entry in result.timeline:
        sign = "+" if entry.event_type == "INFLOW" else "-"
        print(f"  {str(entry.event_date):<12} {entry.description:<30} {entry.event_type:<8} "
              f"{sign}Rs. {entry.amount:>8,.2f}  Rs. {entry.cash_before:>10,.2f}  Rs. {entry.cash_after:>10,.2f}")

    print(f"\n--- Summary ---")
    print(f"  Ending Cash              : Rs. {result.ending_cash:>12,.2f}")
    print(f"  Minimum Projected Cash   : Rs. {result.minimum_projected_cash:>12,.2f}"
          + (f"  (on {result.date_of_minimum_projected_cash})" if result.date_of_minimum_projected_cash else ""))
    print(f"  Projected Shortfall      : "
          + (f"Rs. {result.projected_shortfall:,.2f}" if result.projected_shortfall else "None"))
    print(f"  Total Deferral Cost      : {result.total_deferral_cost:.2f}")

    print("\n--- Structured Decision Factors ---")
    all_decisions = result.selected_obligations + result.deferred_obligations + result.negotiated_obligations
    for od in all_decisions:
        o = od.obligation
        print(f"\n  {o.description or o.counterparty_name} [{od.action}]")
        for factor in od.decision_factors:
            sign = "+" if factor.contribution >= 0 else ""
            print(f"    {factor.factor_name:25s}: raw={factor.raw_value}  "
                  f"weight={factor.weight:+.1f}  contribution={sign}{factor.contribution:.1f}")

    print("\n--- Determinism Verification ---")
    result2 = engine.evaluate_obligations(
        current_cash=Decimal("100000.00"),
        minimum_cash_buffer=Decimal("25000.00"),
        obligations=obligations,
        receivables=receivables,
        as_of_date=date(2026, 9, 1),
        projection_mode=ReceivableMode.RAW,
    )
    paid1 = sorted(od.obligation.payable_id for od in result.selected_obligations)
    paid2 = sorted(od.obligation.payable_id for od in result2.selected_obligations)
    same = paid1 == paid2 and result.total_deferral_cost == result2.total_deferral_cost
    print(f"  Same result on two runs  : {'YES - DETERMINISTIC' if same else 'NO - BUG!'}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    run_stress_test()
