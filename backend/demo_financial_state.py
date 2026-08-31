from datetime import date
from decimal import Decimal

from app.db.database import SessionLocal
from app.models.company import Company
from app.services.financial_state import FinancialStateService
from app.services.cash_flow import CashFlowService
from app.schemas.financial_state import ProjectionMode

def run_demo():
    print("--- CashFin Financial State Demo ---")
    
    with SessionLocal() as session:
        # Find ABC Traders
        company = session.query(Company).filter(Company.name == "ABC Traders").first()
        if not company:
            print("ABC Traders not found in database. Run seed script first.")
            return

        as_of_date = date(2026, 8, 30) # A date before the pending payables in seed data
        
        # 1. Financial State
        state = FinancialStateService.get_financial_state(session, company.id, as_of_date)
        
        print("\n=== CURRENT FINANCIAL STATE ===")
        print(f"Company: {company.name}")
        print(f"As of: {state.as_of_date}")
        print(f"Current Cash: Rs. {state.current_cash:,.2f}")
        print(f"Total Pending Payables: Rs. {state.pending_payables_total:,.2f}")
        print(f"Total Expected Receivables (RAW): Rs. {state.pending_receivables_total_raw:,.2f}")
        
        # 2. Cash Flow Projection
        min_buffer = Decimal('25000.00')
        projection = CashFlowService.calculate_projection(
            state=state,
            minimum_cash_buffer=min_buffer,
            projection_mode=ProjectionMode.RAW
        )
        
        print(f"\n=== CASH FLOW PROJECTION (RAW) ===")
        print(f"Minimum Cash Buffer: Rs. {projection.minimum_cash_buffer:,.2f}")
        
        print("\n--- Chronological Events ---")
        current_balance = projection.starting_balance
        print(f"Starting cash: Rs. {current_balance:,.2f}")
        
        for event in projection.events:
            print(f"\n{event.date.strftime('%b %d')}")
            print(f"{event.description or 'Event'}: {'+' if event.amount > 0 else '-'}Rs. {abs(event.amount):,.2f}")
            current_balance += event.amount
            print(f"Projected cash: Rs. {current_balance:,.2f}")

        print("\n--- Summary ---")
        if projection.days_to_zero is not None:
            print(f"Days to Zero: {projection.days_to_zero} days")
        else:
            print("Days to Zero: Not projected (Cash remains positive)")
            
        if projection.days_to_buffer_breach is not None:
            print(f"Days to Buffer Breach: {projection.days_to_buffer_breach} days")
        else:
            print("Days to Buffer Breach: Not projected (Cash remains above buffer)")
            
        if projection.shortfalls:
            print("\n--- Detected Shortfalls / Breaches ---")
            for breach in projection.shortfalls:
                breach_type = "Zero Breach" if breach.is_zero_breach else "Buffer Breach"
                print(f"Date: {breach.breach_date.strftime('%b %d')}")
                print(f"Projected cash: ₹{breach.projected_balance:,.2f}")
                print(f"Shortfall amount: ₹{breach.shortfall_amount:,.2f}")
                if breach.triggering_event:
                    print(f"Triggering event: {breach.triggering_event.description}")
                print(f"Type: {breach_type}\n")

if __name__ == "__main__":
    run_demo()
