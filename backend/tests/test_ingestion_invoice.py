import pytest
from datetime import date
from decimal import Decimal

from app.ingestion.json_parser import parse_json_string
from app.ingestion.normalizer import normalize_invoice
from app.ingestion.validator import validate_invoice

def test_11_valid_invoice():
    json_content = """[
        {
            "invoice_number": "INV-1234",
            "customer": "XYZ Customer",
            "amount": 60000,
            "invoice_date": "2026-08-20",
            "due_date": "2026-09-10"
        }
    ]"""
    rows, errs = parse_json_string(json_content)
    assert not errs
    norm = normalize_invoice(rows[0])
    assert norm.invoice_number == "INV-1234"
    assert norm.customer_name == "XYZ Customer"
    assert norm.amount == Decimal("60000")
    
    val_errs = validate_invoice(norm, 1)
    assert not val_errs

def test_12_invalid_invoice():
    json_content = """[
        {
            "invoice_number": "INV-1234",
            "customer": "XYZ",
            "amount": -100,
            "invoice_date": "2026-08-20",
            "due_date": "2026-08-10"
        }
    ]"""
    rows, errs = parse_json_string(json_content)
    norm = normalize_invoice(rows[0]) # Amount parsing abs value? The normalizer abs() negative amounts. Let's check logic:
    # Actually, parse_amount returns abs value. But due date is before invoice date.
    val_errs = validate_invoice(norm, 1)
    assert any(e.field == "due_date" for e in val_errs)
