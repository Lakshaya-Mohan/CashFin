import os
import sys
from datetime import date
from decimal import Decimal

# Add backend to path for direct execution
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.company import Company
from app.models.account import Account
from app.services.ingestion_service import (
    ingest_bank_csv,
    ingest_invoices_json,
    ingest_expenses_json,
    ingest_receipt_image,
)
from app.schemas.ingestion import IngestionResult
from app.services.financial_state import FinancialStateService
from app.schemas.financial_state import ProjectionMode

def print_result(title: str, res: IngestionResult):
    print(f"\n--- {title} ---")
    print(f"Total Records: {res.total_records}")
    print(f"Inserted: {res.inserted_records}")
    print(f"Duplicates: {res.duplicate_records}")
    print(f"Possible Duplicates: {res.possible_duplicates}")
    print(f"Failed: {res.failed_records}")
    if res.errors:
        print("Errors:")
        for err in res.errors:
            print(f"  Row {err.row_number}, Field '{err.field}': {err.error_message}")

def setup_demo_company(session):
    company = session.query(Company).filter_by(name="Demo Ingestion Corp").first()
    if not company:
        company = Company(name="Demo Ingestion Corp")
        session.add(company)
        session.commit()
        session.refresh(company)

    account = session.query(Account).filter_by(company_id=company.id, account_name="Main Checking").first()
    if not account:
        account = Account(
            company_id=company.id,
            account_name="Main Checking",
            account_type="CHECKING",
            current_balance=Decimal("100000.00"),
        )
        session.add(account)
        session.commit()
        session.refresh(account)
    
    return company, account

def main():
    print("============================================================")
    print("CashFin — Stage 4 Ingestion Demo")
    print("============================================================")

    session = SessionLocal()
    try:
        company, account = setup_demo_company(session)
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        samples_dir = os.path.join(base_dir, "data", "samples")
        
        # 1. Ingest Bank CSV
        csv_path = os.path.join(samples_dir, "bank_statement.csv")
        res_csv = ingest_bank_csv(csv_path, company.id, account.id, session)
        print_result("Bank Statement CSV Ingestion", res_csv)
        
        # 1a. Re-ingest Bank CSV to prove idempotency
        print("\n--- Re-ingesting Bank Statement CSV (Idempotency Check) ---")
        res_csv2 = ingest_bank_csv(csv_path, company.id, account.id, session)
        print(f"Inserted: {res_csv2.inserted_records}, Duplicates: {res_csv2.duplicate_records}")

        # 2. Ingest Invoices JSON
        inv_path = os.path.join(samples_dir, "invoices.json")
        res_inv = ingest_invoices_json(inv_path, company.id, session)
        print_result("Invoices JSON Ingestion", res_inv)

        # 3. Ingest Expenses JSON
        exp_path = os.path.join(samples_dir, "expenses.json")
        res_exp = ingest_expenses_json(exp_path, company.id, account.id, session, as_of_date=date(2026, 8, 31))
        print_result("Expenses JSON Ingestion", res_exp)

        # 4. OCR
        print("\n--- OCR Receipt Ingestion ---")
        print("Skipping actual OCR execution for this demo script because Tesseract may not be installed.")
        print("Check `test_ingestion_ocr.py` for OCR functionality testing.")

        # 5. Financial State Check
        print("\n--- Current Financial State ---")
        state = FinancialStateService.get_financial_state(
            session=session,
            company_id=company.id,
            as_of_date=date(2026, 8, 31)
        )
        
        print(f"Current Cash: Rs. {state.current_cash:,.2f}")
        print("Upcoming Expected Receivables (from invoices):")
        for rec in state.upcoming_receivables:
            print(f"  Rs. {rec.amount:,.2f} due {rec.expected_date}")
            
        print("Upcoming Pending Payables (from future expenses):")
        for pay in state.upcoming_payables:
            print(f"  Rs. {pay.amount:,.2f} due {pay.due_date}")

    finally:
        session.close()

if __name__ == "__main__":
    main()
