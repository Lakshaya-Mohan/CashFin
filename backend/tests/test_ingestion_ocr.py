import pytest
from datetime import date
from decimal import Decimal

from app.ingestion.ocr_extractor import extract_from_text
from app.schemas.ingestion import ExtractionStatus

def test_16_valid_printed_receipt():
    raw = "XYZ Hardware Store\nReceipt # 12345\nDate: 2026-08-31\nAmount: Rs. 1,500.50\nThank you!"
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.COMPLETE
    assert res.vendor == "XYZ Hardware Store"
    assert res.amount == Decimal("1500.50")
    assert res.receipt_date == date(2026, 8, 31)
    assert res.receipt_number == "12345"

def test_17_indian_rupee_amount_format():
    raw = "Vendor A\nDate: 31-08-2026\nTotal: ₹12,500\n"
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.COMPLETE
    assert res.amount == Decimal("12500")

def test_18_different_date_formats():
    raw = "Vendor B\nDate: 31 Aug 2026\nTotal: 1000\n"
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.COMPLETE
    assert res.receipt_date == date(2026, 8, 31)

def test_19_missing_amount():
    raw = "Vendor C\nDate: 2026-08-31\n"
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.NEEDS_REVIEW
    assert res.amount is None

def test_20_missing_vendor():
    raw = "Receipt\nTotal: 100\nDate: 2026-08-31\n"
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.NEEDS_REVIEW
    assert res.vendor is None

def test_21_ocr_failure():
    raw = ""
    res = extract_from_text(raw)
    assert res.extraction_status == ExtractionStatus.FAILED
