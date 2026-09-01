"""
tests/test_api.py — Stage 6 API layer tests

Covering all 24 required API test scenarios:
1. Health endpoint succeeds
2. Database failure handled
3. List companies
4. Get existing company
5. Unknown company returns 404
6. Existing company returns correct financial state
7. Invalid date rejected
8. Financial state unknown company returns 404
9. Projection endpoint returns chronological events
10. Forecast mode is respected
11. Buffer parameter is respected
12. Forecast endpoint returns predictions when model exists
13. Missing model handled correctly
14. Invalid horizon rejected
15. Decision endpoint returns DecisionResult
16. Deterministic result across repeated identical requests
17. Minimum buffer is respected
18. Decision unknown company returns 404
19. Valid CSV upload
20. Duplicate CSV upload
21. Valid invoice import
22. Valid expense import
23. Valid receipt upload
24. Invalid file/input handling
"""

import os
import json
import pytest
from datetime import date, timedelta
from decimal import Decimal

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
from app.ml.forecaster import ForecasterService

# Use SQLite in-memory for fast, isolated API tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create fresh tables and seed sample data before each test."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()

    # Seed Company 1
    c1 = Company(id=1, name="Acme Corp", industry="Technology")
    db.add(c1)
    db.flush()

    # Seed Account 1
    a1 = Account(id=1, company_id=1, account_name="Operating Account", account_type="BANK", current_balance=Decimal("100000.00"))
    db.add(a1)
    db.flush()

    # Seed Counterparty
    cp1 = Counterparty(id=1, company_id=1, name="Supplier Co", counterparty_type="SUPPLIER")
    db.add(cp1)
    db.flush()

    # Seed Payables
    p1 = Payable(id=1, company_id=1, counterparty_id=1, amount=Decimal("20000.00"), due_date=date.today() + timedelta(days=5), status="PENDING", urgency=5, penalty_risk=4, flexibility=1, description="Raw materials")
    p2 = Payable(id=2, company_id=1, counterparty_id=1, amount=Decimal("15000.00"), due_date=date.today() + timedelta(days=10), status="PENDING", urgency=3, penalty_risk=2, flexibility=4, description="Office Supplies")
    db.add_all([p1, p2])

    # Seed Receivable
    r1 = Receivable(id=1, company_id=1, counterparty_id=1, amount=Decimal("30000.00"), expected_date=date.today() + timedelta(days=7), confidence=Decimal("0.90"), status="EXPECTED", description="Consulting Fee")
    db.add(r1)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Health Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_1_health_endpoint_succeeds():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_2_health_endpoint_database_failure():
    """Test database connection failure handling."""
    def broken_get_db():
        broken_engine = create_engine("sqlite:///non_existent_dir/broken.db")
        broken_session = sessionmaker(bind=broken_engine)()
        try:
            yield broken_session
        finally:
            broken_session.close()

    app.dependency_overrides[get_db] = broken_get_db
    try:
        response = client.get("/api/v1/health")
        assert response.status_code in (500, 503)
        assert response.json()["status"] == "error"
    finally:
        app.dependency_overrides[get_db] = override_get_db


# ─────────────────────────────────────────────────────────────────────────────
# 2. Company Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_3_list_companies():
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "Acme Corp"


def test_4_get_existing_company():
    response = client.get("/api/v1/companies/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Acme Corp"


def test_5_unknown_company_returns_404():
    response = client.get("/api/v1/companies/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Financial State Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_6_existing_company_returns_financial_state():
    response = client.get("/api/v1/companies/1/financial-state")
    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == 1
    assert float(data["current_cash"]) == 100000.0
    assert len(data["upcoming_payables"]) == 2
    assert len(data["upcoming_receivables"]) == 1


def test_7_invalid_date_rejected():
    response = client.get("/api/v1/companies/1/financial-state?as_of_date=invalid-date")
    assert response.status_code == 422


def test_8_financial_state_unknown_company_returns_404():
    response = client.get("/api/v1/companies/999/financial-state")
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 4. Cash Flow Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_9_cash_flow_projection_returns_events():
    response = client.get("/api/v1/companies/1/cash-flow")
    assert response.status_code == 200
    data = response.json()
    assert "starting_balance" in data
    assert "events" in data
    assert isinstance(data["events"], list)
    assert len(data["events"]) == 3  # 2 payables + 1 receivable


def test_10_cash_flow_forecast_mode_respected():
    response = client.get("/api/v1/companies/1/cash-flow?forecast_mode=CONFIRMED_ONLY")
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_mode"] == "CONFIRMED_ONLY"
    assert all(not e["is_predicted"] for e in data["events"])


def test_11_cash_flow_buffer_parameter_respected():
    response = client.get("/api/v1/companies/1/cash-flow?minimum_cash_buffer=50000")
    assert response.status_code == 200
    data = response.json()
    assert float(data["minimum_cash_buffer"]) == 50000.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Forecast Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_12_forecast_endpoint_returns_predictions_when_model_exists(monkeypatch, tmp_path):
    import app.ml.forecaster as fc_module
    monkeypatch.setattr(fc_module, "MODELS_DIR", str(tmp_path))

    # Train a dummy forecaster to create saved model
    import pandas as pd
    import numpy as np
    rng = np.random.default_rng(42)
    rows = []
    start = date.today() - timedelta(days=90)
    for i in range(90):
        d = start + timedelta(days=i)
        rows.append({
            "transaction_date": d,
            "amount": float(rng.uniform(5000, 20000)),
            "transaction_type": "INCOME" if i % 2 == 0 else "EXPENSE"
        })
    df = pd.DataFrame(rows)

    forecaster = ForecasterService(random_state=42)
    forecaster.train_and_evaluate(df)

    # Populate DB transactions for company 1
    db = TestingSessionLocal()
    for row in rows:
        t = Transaction(
            account_id=1,
            transaction_date=row["transaction_date"],
            amount=Decimal(str(round(row["amount"], 2))),
            transaction_type=row["transaction_type"],
            description="Test Txn",
            category="General",
            source="test"
        )
        db.add(t)
    db.commit()
    db.close()

    response = client.get("/api/v1/companies/1/forecast?horizon_days=14")
    assert response.status_code == 200
    data = response.json()
    assert data["company_id"] == 1
    assert data["horizon_days"] == 14
    assert len(data["events"]) == 14


def test_13_missing_model_handled_correctly(monkeypatch, tmp_path):
    import app.ml.forecaster as fc_module
    monkeypatch.setattr(fc_module, "MODELS_DIR", str(tmp_path))

    response = client.get("/api/v1/companies/1/forecast")
    assert response.status_code == 400
    assert "model has not been trained" in response.json()["detail"]


def test_14_invalid_horizon_rejected():
    response = client.get("/api/v1/companies/1/forecast?horizon_days=150")
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 6. Decision Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_15_decision_endpoint_returns_decision_result():
    payload = {
        "as_of_date": str(date.today()),
        "minimum_cash_buffer": 25000,
        "receivable_mode": "RAW",
        "forecast_mode": "CONFIRMED_ONLY"
    }
    response = client.post("/api/v1/companies/1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "feasible" in data
    assert "initial_cash" in data
    assert "selected_obligations" in data


def test_16_deterministic_result_across_repeated_requests():
    payload = {
        "as_of_date": str(date.today()),
        "minimum_cash_buffer": 25000,
        "receivable_mode": "RAW",
        "forecast_mode": "CONFIRMED_ONLY"
    }
    res1 = client.post("/api/v1/companies/1/decision", json=payload).json()
    res2 = client.post("/api/v1/companies/1/decision", json=payload).json()
    assert res1["feasible"] == res2["feasible"]
    assert len(res1["selected_obligations"]) == len(res2["selected_obligations"])


def test_17_decision_minimum_buffer_respected():
    payload = {
        "minimum_cash_buffer": 200000  # Cash is 100k, buffer 200k -> infeasible
    }
    response = client.post("/api/v1/companies/1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["feasible"] is False


def test_18_decision_unknown_company_returns_404():
    payload = {"minimum_cash_buffer": 10000}
    response = client.post("/api/v1/companies/999/decision", json=payload)
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 7. Ingestion Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_19_valid_csv_upload():
    csv_content = (
        "date,description,amount,type,reference\n"
        "2026-08-20,UPI PAYMENT SUPPLIER,12500,DEBIT,TXN_API_001\n"
    )
    files = {"file": ("bank.csv", csv_content.encode("utf-8"), "text/csv")}
    response = client.post("/api/v1/companies/1/accounts/1/transactions/import", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 1
    assert data["inserted_records"] == 1


def test_20_duplicate_csv_upload():
    csv_content = (
        "date,description,amount,type,reference\n"
        "2026-08-20,UPI PAYMENT DUP,12500,DEBIT,TXN_DUP_001\n"
    )
    files1 = {"file": ("bank.csv", csv_content.encode("utf-8"), "text/csv")}
    res1 = client.post("/api/v1/companies/1/accounts/1/transactions/import", files=files1)
    assert res1.json()["inserted_records"] == 1

    files2 = {"file": ("bank.csv", csv_content.encode("utf-8"), "text/csv")}
    res2 = client.post("/api/v1/companies/1/accounts/1/transactions/import", files=files2)
    assert res2.json()["duplicate_records"] == 1
    assert res2.json()["inserted_records"] == 0


def test_21_valid_invoice_import():
    invoices_json = [
        {
            "invoice_number": "INV-API-001",
            "customer_name": "Acme Customer",
            "amount": 45000.0,
            "invoice_date": "2026-08-01",
            "due_date": "2026-08-30",
            "description": "API Ingest Invoice"
        }
    ]
    response = client.post("/api/v1/companies/1/invoices/import", json=invoices_json)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 1
    assert data["inserted_records"] == 1


def test_22_valid_expense_import():
    expenses_json = [
        {
            "vendor_name": "API Vendor Co",
            "amount": 8500.0,
            "expense_date": "2026-08-15",
            "description": "API Ingest Expense",
            "is_future_obligation": True,
            "due_date": "2026-09-15"
        }
    ]
    response = client.post("/api/v1/companies/1/expenses/import", json=expenses_json)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 1
    assert data["inserted_records"] == 1


def test_23_valid_receipt_upload(tmp_path):
    from PIL import Image
    img_path = tmp_path / "receipt.jpg"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(img_path)

    with open(img_path, "rb") as f:
        files = {"file": ("receipt.jpg", f, "image/jpeg")}
        response = client.post("/api/v1/companies/1/accounts/1/receipts", files=files)

    assert response.status_code == 200
    data = response.json()
    assert "total_records" in data


def test_24_invalid_file_input_handling():
    files = {"file": ("bad_file.txt", b"Not a CSV or image", "text/plain")}
    response = client.post("/api/v1/companies/1/accounts/1/transactions/import", files=files)
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["detail"]
