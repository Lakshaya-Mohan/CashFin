"""
Normalizer — Stage 4

Responsibility: Convert raw parsed dicts (from csv_parser / json_parser) into
typed, canonical CashFin schemas (NormalizedTransaction, NormalizedInvoice,
NormalizedExpense).

Does NOT query the database. Does NOT validate completeness (that is the
validator's job). Does NOT compute fingerprints (fingerprints require account_id
which is a service-level concern — computed in ingestion_service).

Raises ValueError on irrecoverable parse failures so callers can log them as
row-level errors without crashing the whole pipeline.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from app.schemas.ingestion import (
    NormalizedExpense,
    NormalizedInvoice,
    NormalizedTransaction,
    TransactionType,
)

# ---------------------------------------------------------------------------
# Amount parsing helpers
# ---------------------------------------------------------------------------
# Ordered by specificity. Each pattern strips currency symbols/commas and
# returns a clean decimal string.
_AMOUNT_PATTERNS = [
    re.compile(r'[₹]\s*([\d,]+(?:\.\d{1,2})?)'),          # ₹12,500 or ₹12500.00
    re.compile(r'Rs\.?\s*([\d,]+(?:\.\d{1,2})?)'),          # Rs. 12500 or Rs 12500.00
    re.compile(r'INR\s*([\d,]+(?:\.\d{1,2})?)'),             # INR 12500
    re.compile(r'^([\d,]+(?:\.\d{1,2})?)$'),                 # Plain number: 12500.00
]

_DEBIT_KEYWORDS = {"debit", "dr", "d", "withdrawal", "paid out", "expense"}
_CREDIT_KEYWORDS = {"credit", "cr", "c", "deposit", "paid in", "income"}

# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------
_DATE_FORMATS = [
    "%Y-%m-%d",    # 2026-08-31
    "%d/%m/%Y",    # 31/08/2026
    "%d-%m-%Y",    # 31-08-2026
    "%d/%m/%y",    # 31/08/26
    "%d-%m-%y",    # 31-08-26
    "%m/%d/%Y",    # 08/31/2026
    "%d %b %Y",    # 31 Aug 2026
    "%d %B %Y",    # 31 August 2026
    "%b %d, %Y",   # Aug 31, 2026
]


def parse_amount(raw: str) -> Decimal:
    """
    Parse a raw amount string into a positive Decimal.

    Handles: ₹12,500 / Rs. 12,500 / 12500.00 / 12,500
    Negative inputs are returned as their absolute value (direction is encoded
    in TransactionType, not in the amount sign).

    Raises ValueError if parsing fails.
    """
    if not raw or not raw.strip():
        raise ValueError(f"Empty amount string: {raw!r}")

    raw = raw.strip()

    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(raw)
        if match:
            clean = match.group(1).replace(",", "")
            try:
                value = Decimal(clean)
                return abs(value)
            except InvalidOperation:
                continue

    # Last resort: strip everything except digits, period, minus
    cleaned = re.sub(r"[^\d.\-]", "", raw)
    if cleaned:
        try:
            return abs(Decimal(cleaned))
        except InvalidOperation:
            pass

    raise ValueError(f"Cannot parse amount from: {raw!r}")


def parse_date(raw: str) -> date:
    """
    Parse a raw date string into a Python date.
    Tries multiple common formats before raising ValueError.
    """
    if not raw or not raw.strip():
        raise ValueError(f"Empty date string: {raw!r}")

    raw = raw.strip()

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Cannot parse date from: {raw!r} (tried formats: {_DATE_FORMATS})")


def normalize_description(desc: Optional[str]) -> str:
    """
    Produce a normalized (canonical) description string.
    Uppercase + collapse whitespace. Used for fingerprint computation.
    """
    if not desc:
        return ""
    return " ".join(desc.strip().upper().split())


def _parse_transaction_type(raw: str) -> TransactionType:
    """Map raw DEBIT/CREDIT string to TransactionType enum."""
    normalized = raw.strip().lower()
    if normalized in _DEBIT_KEYWORDS:
        return TransactionType.EXPENSE
    if normalized in _CREDIT_KEYWORDS:
        return TransactionType.INCOME
    raise ValueError(f"Unknown transaction type: {raw!r}. Expected DEBIT/CREDIT variants.")


# ---------------------------------------------------------------------------
# Public normalization functions
# ---------------------------------------------------------------------------

def normalize_csv_row(
    raw_row: Dict[str, str],
    source_file: Optional[str] = None,
) -> NormalizedTransaction:
    """
    Convert a raw CSV row dict (from csv_parser) into a NormalizedTransaction.

    The 'transaction_type' column is optional in CSV rows. When missing, the
    engine cannot determine direction and will raise ValueError.

    Fingerprint is NOT computed here — it requires account_id which is
    provided by the ingestion service later.

    Raises ValueError for irrecoverable parse failures.
    """
    txn_date = parse_date(raw_row.get("transaction_date", ""))
    amount = parse_amount(raw_row.get("amount", ""))
    description = raw_row.get("description", "").strip() or None
    external_id = raw_row.get("external_id", "").strip() or None

    type_raw = raw_row.get("transaction_type", "").strip()
    if not type_raw:
        raise ValueError("'transaction_type' (DEBIT/CREDIT) is required but missing.")
    txn_type = _parse_transaction_type(type_raw)

    return NormalizedTransaction(
        transaction_date=txn_date,
        amount=amount,
        transaction_type=txn_type,
        description=description,
        external_id=external_id,
        source="bank_csv",
        source_file=source_file,
    )


def normalize_invoice(raw: Dict[str, Any]) -> NormalizedInvoice:
    """
    Convert a raw invoice dict (from json_parser) into a NormalizedInvoice.

    Accepted field names:
      invoice_number / invoice_no / number
      customer / customer_name / client
      amount / total / total_amount
      invoice_date / date
      due_date / payment_due / due
    Raises ValueError for irrecoverable failures.
    """
    def _get(*keys: str) -> Optional[str]:
        for k in keys:
            v = raw.get(k)
            if v is not None:
                return str(v)
        return None

    invoice_number = _get("invoice_number", "invoice_no", "number")
    if not invoice_number:
        raise ValueError("Invoice number is required (fields: invoice_number, invoice_no, number).")

    customer = _get("customer", "customer_name", "client", "party")
    if not customer:
        raise ValueError("Customer name is required (fields: customer, customer_name, client).")

    raw_amount = _get("amount", "total", "total_amount", "value")
    if raw_amount is None:
        raise ValueError("Amount is required (fields: amount, total, total_amount).")
    amount = parse_amount(raw_amount)

    raw_invoice_date = _get("invoice_date", "date", "issue_date")
    if not raw_invoice_date:
        raise ValueError("Invoice date is required (fields: invoice_date, date).")
    invoice_date = parse_date(raw_invoice_date)

    raw_due_date = _get("due_date", "payment_due", "due", "due_on")
    if not raw_due_date:
        raise ValueError("Due date is required (fields: due_date, payment_due, due).")
    due_date = parse_date(raw_due_date)

    description = _get("description", "notes", "remarks") or None

    raw_confidence = _get("confidence")
    confidence = Decimal(str(raw_confidence)) if raw_confidence else Decimal("0.9")

    return NormalizedInvoice(
        invoice_number=invoice_number.strip(),
        customer_name=customer.strip(),
        amount=amount,
        invoice_date=invoice_date,
        due_date=due_date,
        description=description,
        confidence=confidence,
    )


def normalize_expense(raw: Dict[str, Any], as_of_date: Optional[date] = None) -> NormalizedExpense:
    """
    Convert a raw expense dict into a NormalizedExpense.

    Classification rule (explicit, documented):
      Priority 1: If 'paid' field is explicitly present, use it.
      Priority 2: If 'is_future_obligation' is explicitly set, use it.
      Priority 3 (fallback): Compare expense_date to as_of_date.
                             Past/current → Transaction (paid).
                             Future → Payable (obligation).

    The 'paid' field takes precedence over date-based inference.

    Accepted field names:
      vendor / vendor_name / supplier / payee
      amount / total / value
      expense_date / date / paid_date / purchase_date
      description / details / narration / memo
      external_id / reference / ref
    """
    def _get(*keys: str) -> Optional[str]:
        for k in keys:
            v = raw.get(k)
            if v is not None:
                return str(v)
        return None

    vendor = _get("vendor", "vendor_name", "supplier", "payee")
    if not vendor:
        raise ValueError("Vendor name is required (fields: vendor, vendor_name, supplier, payee).")

    raw_amount = _get("amount", "total", "value")
    if raw_amount is None:
        raise ValueError("Amount is required (fields: amount, total, value).")
    amount = parse_amount(raw_amount)

    raw_date = _get("expense_date", "date", "paid_date", "purchase_date")
    if not raw_date:
        raise ValueError("Expense date is required (fields: expense_date, date, paid_date).")
    expense_date = parse_date(raw_date)

    description = _get("description", "details", "narration", "memo") or None
    external_id = _get("external_id", "reference", "ref", "expense_id") or None

    raw_due_date = _get("due_date", "payment_due", "due")
    due_date = parse_date(raw_due_date) if raw_due_date else None

    # --- Explicit payment status resolution ---
    explicit_paid: Optional[bool] = None
    if "paid" in raw:
        v = raw["paid"]
        if isinstance(v, bool):
            explicit_paid = v
        elif isinstance(v, str):
            explicit_paid = v.lower() in ("true", "yes", "1", "paid")

    explicit_future: Optional[bool] = None
    if "is_future_obligation" in raw:
        v = raw["is_future_obligation"]
        if isinstance(v, bool):
            explicit_future = v
        elif isinstance(v, str):
            explicit_future = v.lower() in ("true", "yes", "1")

    # Resolve is_future_obligation
    if explicit_paid is not None:
        is_future = not explicit_paid           # paid=True → not a future obligation
    elif explicit_future is not None:
        is_future = explicit_future
    else:
        # Documented date-based fallback
        ref_date = as_of_date or date.today()
        is_future = expense_date > ref_date

    if is_future and due_date is None:
        due_date = expense_date  # If no explicit due_date, use expense_date itself

    return NormalizedExpense(
        vendor_name=vendor.strip(),
        amount=amount,
        expense_date=expense_date,
        description=description,
        external_id=external_id,
        is_future_obligation=is_future,
        due_date=due_date,
        paid=explicit_paid,
    )
