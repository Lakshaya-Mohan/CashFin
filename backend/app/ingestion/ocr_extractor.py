"""
OCR Extractor — Stage 4

Responsibility: Extract structured financial data from receipt images using
Tesseract OCR and deterministic regex patterns.

Architecture:
  image_path → OCR text (pytesseract) → extract_from_text() → ExtractedReceipt

The text extraction pipeline (extract_from_text) is fully deterministic and
testable without an actual image file or Tesseract installation.
All OCR tests should call extract_from_text() directly with controlled text.

SETUP REQUIREMENT:
  pip install pytesseract Pillow
  + Tesseract binary must be on PATH (https://github.com/UB-Mannheim/tesseract/wiki)
  Windows: typically C:\\Program Files\\Tesseract-OCR\\tesseract.exe

If pytesseract or Pillow are not installed, extract_from_image() returns
ExtractionStatus.FAILED gracefully without crashing.

IMPORTANT: raw_text is always preserved in ExtractedReceipt, even on failure.
This is critical for debugging and future AI-assisted re-extraction.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.schemas.ingestion import ExtractionStatus, ExtractedReceipt

# ---------------------------------------------------------------------------
# Try importing optional dependencies
# ---------------------------------------------------------------------------
try:
    import pytesseract
    from PIL import Image
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Regex patterns for deterministic field extraction
# ---------------------------------------------------------------------------

# Amount patterns (tried in order of specificity)
_AMOUNT_RE = [
    re.compile(r'[₹]\s*([\d,]+(?:\.\d{1,2})?)'),                  # ₹12,500
    re.compile(r'Rs\.?\s*([\d,]+(?:\.\d{1,2})?)'),                  # Rs. 12500
    re.compile(r'INR\s*([\d,]+(?:\.\d{1,2})?)'),                    # INR 12500
    re.compile(r'(?:Total|Amount|Grand\s*Total|TOTAL)\s*:?\s*([\d,]+(?:\.\d{1,2})?)'),
    re.compile(r'(?:^|\s)([\d,]{3,}(?:\.\d{1,2})?)(?:\s|$)'),      # Standalone number ≥3 digits
]

# Date patterns (tried in order)
_DATE_PATTERNS = [
    (re.compile(r'(\d{4}-\d{2}-\d{2})'),           "%Y-%m-%d"),    # 2026-08-31
    (re.compile(r'(\d{1,2}/\d{1,2}/\d{4})'),       "%d/%m/%Y"),    # 31/08/2026
    (re.compile(r'(\d{1,2}-\d{1,2}-\d{4})'),       "%d-%m-%Y"),    # 31-08-2026
    (re.compile(r'(\d{1,2}/\d{1,2}/\d{2})'),       "%d/%m/%y"),    # 31/08/26
    (re.compile(r'(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})'), "%d %b %Y"), # 31 Aug 2026
]

# Receipt/invoice number pattern
_RECEIPT_NO_RE = re.compile(
    r'(?:Invoice|Receipt|Bill|Ref|No\.?|#)[#:.\s]*([A-Z0-9][A-Z0-9\-/]{2,})',
    re.IGNORECASE,
)

# Lines that are likely vendor names (not numbers/dates/keywords)
_SKIP_LINE_RE = re.compile(
    r'^(\d|Receipt|Invoice|Bill|Date|Amount|Total|Rs|INR|GST|Tax|Thank)',
    re.IGNORECASE,
)


def _extract_amount(text: str) -> Optional[Decimal]:
    """Extract the most prominent monetary amount from OCR text."""
    for pattern in _AMOUNT_RE:
        match = pattern.search(text)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                return Decimal(raw)
            except InvalidOperation:
                continue
    return None


def _extract_date(text: str) -> Optional[date]:
    """Extract the first recognizable date from OCR text."""
    for pattern, fmt in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt).date()
            except ValueError:
                continue
    return None


def _extract_receipt_number(text: str) -> Optional[str]:
    """Extract a receipt/invoice/reference number from OCR text."""
    match = _RECEIPT_NO_RE.search(text)
    return match.group(1).strip() if match else None


def _extract_vendor(text: str) -> Optional[str]:
    """
    Heuristic vendor extraction: take the first non-empty, non-numeric,
    non-keyword line from the OCR text. Typically the vendor name appears
    at the top of a receipt.
    """
    for line in text.split("\n"):
        line = line.strip()
        if len(line) < 3:
            continue
        if _SKIP_LINE_RE.match(line):
            continue
        if re.fullmatch(r'[\d\s\-/.,]+', line):
            continue
        return line
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_from_text(raw_text: str) -> ExtractedReceipt:
    """
    Extract financial fields from raw OCR text using deterministic regex patterns.

    This function is the testable core of the OCR pipeline. Call it directly
    in tests by providing controlled text strings — no image or Tesseract needed.

    Extraction status logic:
      COMPLETE      — vendor, amount, and date all extracted
      PARTIAL       — at least one key field extracted (receipt_number or description)
      NEEDS_REVIEW  — missing amount or date (critical for financial processing)
      FAILED        — no fields extracted at all
    """
    vendor = _extract_vendor(raw_text)
    amount = _extract_amount(raw_text)
    txn_date = _extract_date(raw_text)
    receipt_number = _extract_receipt_number(raw_text)

    validation_errors = []
    if not amount:
        validation_errors.append("Could not extract a monetary amount from the receipt text.")
    if not txn_date:
        validation_errors.append("Could not extract a date from the receipt text.")
    if not vendor:
        validation_errors.append("Could not identify a vendor name from the receipt text.")

    # Determine status
    if amount and txn_date and vendor:
        status = ExtractionStatus.COMPLETE
    elif not raw_text.strip():
        status = ExtractionStatus.FAILED
    else:
        status = ExtractionStatus.NEEDS_REVIEW

    return ExtractedReceipt(
        vendor=vendor,
        amount=amount,
        receipt_date=txn_date,
        receipt_number=receipt_number,
        description=None,    # Populated by caller if needed
        raw_text=raw_text,
        extraction_status=status,
        validation_errors=validation_errors,
    )


def extract_from_image(image_path: str) -> ExtractedReceipt:
    """
    Run Tesseract OCR on an image file and extract receipt fields.

    Returns ExtractedReceipt with status=FAILED if:
      - pytesseract or Pillow are not installed
      - Tesseract binary is not found
      - The image file cannot be opened

    raw_text is always preserved for debugging.
    """
    if not _TESSERACT_AVAILABLE:
        return ExtractedReceipt(
            raw_text="",
            extraction_status=ExtractionStatus.FAILED,
            validation_errors=[
                "pytesseract or Pillow not installed. "
                "Install with: pip install pytesseract Pillow "
                "and ensure Tesseract binary is on PATH."
            ],
        )

    try:
        image = Image.open(image_path)
        raw_text = pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError:
        return ExtractedReceipt(
            raw_text="",
            extraction_status=ExtractionStatus.FAILED,
            validation_errors=[
                "Tesseract binary not found on PATH. "
                "Install from https://github.com/UB-Mannheim/tesseract/wiki "
                "and ensure it is accessible."
            ],
        )
    except FileNotFoundError:
        return ExtractedReceipt(
            raw_text="",
            extraction_status=ExtractionStatus.FAILED,
            validation_errors=[f"Image file not found: {image_path}"],
        )
    except Exception as e:
        return ExtractedReceipt(
            raw_text="",
            extraction_status=ExtractionStatus.FAILED,
            validation_errors=[f"OCR processing failed: {str(e)}"],
        )

    return extract_from_text(raw_text)
