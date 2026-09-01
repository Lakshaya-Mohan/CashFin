#!/usr/bin/env python
"""
demo_api.py — Stage 6: CashFin FastAPI API Layer Demo

Demonstrates the CashFin REST API layer using FastAPI TestClient to simulate HTTP requests.

Endpoints demonstrated:
  1. GET /api/v1/health
  2. GET /api/v1/companies
  3. GET /api/v1/companies/{company_id}
  4. GET /api/v1/companies/{company_id}/financial-state
  5. GET /api/v1/companies/{company_id}/cash-flow
  6. GET /api/v1/companies/{company_id}/forecast
  7. POST /api/v1/companies/{company_id}/decision
  8. POST /api/v1/companies/{company_id}/accounts/{account_id}/transactions/import

Run: python demo_api.py
"""

import sys
import os
import io
import json
from datetime import date, timedelta
from decimal import Decimal

# Ensure UTF-8 output encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.database import get_db
from app.models.company import Company
from app.models.account import Account
from app.models.payable import Payable
from app.models.receivable import Receivable
from app.models.transaction import Transaction
from app.models.counterparty import Counterparty
from app.ml.forecaster import ForecasterService, MODELS_DIR

# Setup test DB
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine)


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def seed_demo_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Company
    c = Company(id=1, name="ABC Enterprises", industry="Manufacturing")
    db.add(c)
    db.flush()

    # Account
    acc = Account(id=1, company_id=1, account_name="Main HDFC Account", account_type="BANK", current_balance=Decimal("150000.00"))
    db.add(acc)
    db.flush()

    # Counterparties
    cp1 = Counterparty(id=1, company_id=1, name="Steel Supplier Corp", counterparty_type="SUPPLIER")
    cp2 = Counterparty(id=2, company_id=1, name="Tech Customer Ltd", counterparty_type="CUSTOMER")
    db.add_all([cp1, cp2])
    db.flush()

    # Payables
    p1 = Payable(id=1, company_id=1, counterparty_id=1, amount=Decimal("40000.00"), due_date=date.today() + timedelta(days=5), status="PENDING", urgency=5, penalty_risk=4, flexibility=1, description="Raw materials invoice #881")
    p2 = Payable(id=2, company_id=1, counterparty_id=1, amount=Decimal("30000.00"), due_date=date.today() + timedelta(days=12), status="PENDING", urgency=3, penalty_risk=2, flexibility=4, description="Equipment maintenance")
    db.add_all([p1, p2])

    # Receivable
    r1 = Receivable(id=1, company_id=1, counterparty_id=2, amount=Decimal("60000.00"), expected_date=date.today() + timedelta(days=8), confidence=Decimal("0.85"), status="EXPECTED", description="Q3 Service Fee")
    db.add(r1)

    db.commit()

    # Train dummy model so forecast endpoint works
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(42)
    rows = []
    start = date.today() - timedelta(days=90)
    for i in range(90):
        d = start + timedelta(days=i)
        amt = float(rng.uniform(5000, 25000))
        t_type = "INCOME" if i % 2 == 0 else "EXPENSE"
        rows.append({"transaction_date": d, "amount": amt, "transaction_type": t_type})
        db.add(Transaction(account_id=1, transaction_date=d, amount=Decimal(str(round(amt, 2))), transaction_type=t_type, description="Historical Txn", category="General", source="demo"))

    db.commit()
    db.close()

    df = pd.DataFrame(rows)
    forecaster = ForecasterService(random_state=42)
    forecaster.train_and_evaluate(df)


def print_section(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    print_section("CashFin Stage 6 API Demo")
    seed_demo_data()
    client = TestClient(app)

    # 1. Health
    print_section("1. GET /api/v1/health")
    res = client.get("/api/v1/health")
    print(f"Status Code : {res.status_code}")
    print(f"Response    : {json.dumps(res.json(), indent=2)}")

    # 2. Companies
    print_section("2. GET /api/v1/companies")
    res = client.get("/api/v1/companies")
    print(f"Status Code : {res.status_code}")
    print(f"Response    : {json.dumps(res.json(), indent=2)}")

    # 3. Financial State
    print_section("3. GET /api/v1/companies/1/financial-state")
    res = client.get("/api/v1/companies/1/financial-state")
    print(f"Status Code : {res.status_code}")
    data = res.json()
    print(f"Company ID                 : {data['company_id']}")
    print(f"Current Cash               : ₹{data['current_cash']}")
    print(f"Pending Payables Total     : ₹{data['pending_payables_total']}")
    print(f"Upcoming Payables Count    : {len(data['upcoming_payables'])}")
    print(f"Upcoming Receivables Count : {len(data['upcoming_receivables'])}")

    # 4. Cash Flow Projection
    print_section("4. GET /api/v1/companies/1/cash-flow?horizon_days=14&minimum_cash_buffer=25000")
    res = client.get("/api/v1/companies/1/cash-flow?horizon_days=14&minimum_cash_buffer=25000")
    print(f"Status Code : {res.status_code}")
    data = res.json()
    print(f"Starting Balance           : ₹{data['starting_balance']}")
    print(f"Minimum Cash Buffer        : ₹{data['minimum_cash_buffer']}")
    print(f"Events Count               : {len(data['events'])}")
    print(f"Minimum Projected Balance  : ₹{data['minimum_projected_balance']}")

    # 5. Forecast
    print_section("5. GET /api/v1/companies/1/forecast?horizon_days=7")
    res = client.get("/api/v1/companies/1/forecast?horizon_days=7")
    print(f"Status Code : {res.status_code}")
    data = res.json()
    print(f"Model Name                 : {data['model_name']} v{data['model_version']}")
    print(f"Horizon Days               : {data['horizon_days']}")
    print(f"Predicted Inflows Total    : ₹{data['total_predicted_inflow']}")
    print(f"Predicted Outflows Total   : ₹{data['total_predicted_outflow']}")

    # 6. Decision
    print_section("6. POST /api/v1/companies/1/decision")
    payload = {
        "as_of_date": str(date.today()),
        "minimum_cash_buffer": 25000,
        "receivable_mode": "RAW",
        "forecast_mode": "CONFIRMED_ONLY"
    }
    res = client.post("/api/v1/companies/1/decision", json=payload)
    print(f"Status Code : {res.status_code}")
    data = res.json()
    print(f"Feasible                   : {data['feasible']}")
    print(f"Initial Cash               : ₹{data['initial_cash']}")
    print(f"Selected Obligations Count : {len(data['selected_obligations'])}")
    print(f"Deferred Obligations Count : {len(data['deferred_obligations'])}")
    print(f"Ending Cash                : ₹{data['ending_cash']}")

    # 7. Ingestion
    print_section("7. POST /api/v1/companies/1/accounts/1/transactions/import (CSV)")
    csv_content = (
        "date,description,amount,type,reference\n"
        "2026-09-01,Supplier Payment API Demo,15000,DEBIT,TXN_DEMO_99\n"
    )
    files = {"file": ("bank_statement.csv", csv_content.encode("utf-8"), "text/csv")}
    res = client.post("/api/v1/companies/1/accounts/1/transactions/import", files=files)
    print(f"Status Code : {res.status_code}")
    data = res.json()
    print(f"Total Records              : {data['total_records']}")
    print(f"Inserted Records           : {data['inserted_records']}")
    print(f"Duplicate Records          : {data['duplicate_records']}")

    print("\n" + "=" * 60)
    print("  Stage 6 API Layer Demo Complete — All Endpoints Functional!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
