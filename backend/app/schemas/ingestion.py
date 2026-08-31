"""
CashFin Ingestion Schemas — Stage 4

Defines the normalized internal representations produced by the ingestion pipeline.
These schemas are decoupled from the SQLAlchemy ORM layer.
"""
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class TransactionType(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class DuplicateStatus(str, Enum):
    NEW = "NEW"
    DUPLICATE = "DUPLICATE"          # Exact match (external_id or fingerprint hit)
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"  # Fingerprint-only match (soft signal)


class ExtractionStatus(str, Enum):
    COMPLETE = "COMPLETE"            # All key fields extracted
    PARTIAL = "PARTIAL"              # Some fields missing but enough to proceed
    NEEDS_REVIEW = "NEEDS_REVIEW"    # Critical fields missing; do not auto-insert
    FAILED = "FAILED"                # OCR or parsing completely failed


class ValidationError(BaseModel):
    row_number: int
    field: str
    error_message: str
    original_value: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NormalizedTransaction(BaseModel):
    """
    Internal representation of a single bank statement transaction.

    Separation of identifiers:
      - external_id: identifier supplied by the source (e.g. bank reference/TXN ID).
                     Never overwritten with computed values.
      - fingerprint: CashFin-computed SHA-256 duplicate-detection signal.
                     SHA-256(account_id|date|amount|normalized_description|transaction_type).
                     Soft signal only — not a globally unique business identifier.
    """
    transaction_date: date
    amount: Decimal                          # Always positive; direction encoded in transaction_type
    transaction_type: TransactionType
    description: Optional[str] = None
    external_id: Optional[str] = None       # Bank-provided reference ID (if any)
    fingerprint: Optional[str] = None       # Computed after account_id is known
    source: str = "bank_csv"
    source_file: Optional[str] = None
    category: str = "Uncategorized"

    model_config = ConfigDict(from_attributes=True)


class NormalizedInvoice(BaseModel):
    """Normalized representation of a customer invoice (maps to Receivable)."""
    invoice_number: str                     # Also used as external_id on Receivable
    customer_name: str
    amount: Decimal
    invoice_date: date
    due_date: date
    description: Optional[str] = None
    confidence: Decimal = Decimal("0.9")

    model_config = ConfigDict(from_attributes=True)


class NormalizedExpense(BaseModel):
    """
    Normalized representation of an expense record.

    Classification rule (explicit, in priority order):
      1. If 'paid' field is explicitly provided in source data, use it.
      2. If 'is_future_obligation' is explicitly set, use it.
      3. Fallback (documented): past/current date → Transaction (paid); future date → Payable.

    The 'is_future_obligation' field MUST be set by the normalizer before
    the ingestion service uses it. The service does NOT guess.
    """
    vendor_name: str
    amount: Decimal
    expense_date: date
    description: Optional[str] = None
    external_id: Optional[str] = None      # Expense/PO reference if provided
    is_future_obligation: bool = False      # True → Payable; False → Transaction
    due_date: Optional[date] = None         # Required when is_future_obligation = True
    paid: Optional[bool] = None             # Explicit source-provided payment status

    model_config = ConfigDict(from_attributes=True)


class ExtractedReceipt(BaseModel):
    """
    Output of the OCR pipeline.

    raw_text is preserved intentionally for debugging and future AI processing.
    Do not discard raw_text even when extraction is complete.
    """
    vendor: Optional[str] = None
    amount: Optional[Decimal] = None
    receipt_date: Optional[date] = None
    receipt_number: Optional[str] = None
    description: Optional[str] = None
    raw_text: str = ""
    extraction_status: ExtractionStatus = ExtractionStatus.NEEDS_REVIEW
    validation_errors: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class RecordResult(BaseModel):
    """Processing outcome for a single ingested record."""
    row_number: int
    duplicate_status: DuplicateStatus = DuplicateStatus.NEW
    inserted: bool = False
    validation_errors: List[ValidationError] = []
    record: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class IngestionResult(BaseModel):
    """
    Summary of a complete ingestion run.
    Designed to be returned directly by API endpoints in a later stage.
    """
    total_records: int
    inserted_records: int
    duplicate_records: int
    possible_duplicates: int
    failed_records: int
    errors: List[ValidationError] = []
    record_results: List[RecordResult] = []

    model_config = ConfigDict(from_attributes=True)
