"""
Duplicate Detector — Stage 4

Responsibility: Determine whether a normalized record already exists in the database.
Uses two separate, independent signals for transactions:

  1. external_id (hard match) — bank-provided reference. If present and matches,
     the record is unambiguously a DUPLICATE.

  2. fingerprint (soft match) — CashFin-computed SHA-256 hash of:
     SHA-256(account_id | date | amount | normalized_description | transaction_type)
     If only the fingerprint matches (no external_id), the record is a
     POSSIBLE_DUPLICATE. It may be a legitimate repeat transaction that happens
     to share all observable attributes.

IMPORTANT:
  - external_id and fingerprint serve different purposes. Do NOT store fingerprints
    in the external_id field.
  - Fingerprint is NOT a globally unique business identifier. It is a deterministic
    duplicate-detection signal. Two genuinely distinct transactions could theoretically
    share a fingerprint (hash collision is astronomically unlikely for SHA-256 but
    is still a soft signal by design).

For invoices: check receivables.external_id = invoice_number.
For expenses/payables: check payables.external_id.
"""
import hashlib
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.payable import Payable
from app.models.receivable import Receivable
from app.models.transaction import Transaction
from app.schemas.ingestion import DuplicateStatus


def compute_transaction_fingerprint(
    account_id: int,
    transaction_date: date,
    amount: Decimal,
    description: Optional[str],
    transaction_type: str,
) -> str:
    """
    Compute a deterministic SHA-256 fingerprint for a transaction.

    Inputs:
      account_id        — int (ensures cross-account legitimacy)
      transaction_date  — date
      amount            — Decimal (formatted to 2 decimal places)
      description       — normalized (uppercase, collapsed whitespace)
      transaction_type  — "INCOME" or "EXPENSE"

    Returns a 64-character lowercase hexadecimal string.

    This fingerprint is a DUPLICATE-DETECTION SIGNAL, not a globally unique
    business identifier. Two identical-looking transactions from the same
    account on the same day produce the same fingerprint and are flagged as
    POSSIBLE_DUPLICATE for human review.
    """
    normalized_desc = " ".join((description or "").strip().upper().split())
    amount_str = f"{amount:.2f}"
    raw = f"{account_id}|{transaction_date}|{amount_str}|{normalized_desc}|{transaction_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_transaction_duplicate(
    session: Session,
    external_id: Optional[str],
    fingerprint: str,
) -> DuplicateStatus:
    """
    Determine if a transaction already exists.

    Priority:
      1. external_id match → DUPLICATE (hard match, bank provided)
      2. fingerprint match → POSSIBLE_DUPLICATE (soft match, computed)
      3. No match          → NEW
    """
    if external_id:
        existing = session.query(Transaction).filter(
            Transaction.external_id == external_id
        ).first()
        if existing:
            return DuplicateStatus.DUPLICATE

    existing_fp = session.query(Transaction).filter(
        Transaction.fingerprint == fingerprint
    ).first()
    if existing_fp:
        return DuplicateStatus.POSSIBLE_DUPLICATE

    return DuplicateStatus.NEW


def check_invoice_duplicate(
    session: Session,
    invoice_number: str,
    company_id: int,
) -> DuplicateStatus:
    """
    Check if an invoice (receivable) with this invoice number already exists
    for the given company.

    Returns DUPLICATE if found, NEW otherwise.
    """
    existing = session.query(Receivable).filter(
        Receivable.external_id == invoice_number,
        Receivable.company_id == company_id,
    ).first()
    return DuplicateStatus.DUPLICATE if existing else DuplicateStatus.NEW


def check_expense_duplicate(
    session: Session,
    external_id: Optional[str],
    company_id: int,
) -> DuplicateStatus:
    """
    Check if an expense (payable) with this external_id already exists
    for the given company. Only used when external_id is provided.

    Returns DUPLICATE if found, NEW otherwise.
    """
    if not external_id:
        return DuplicateStatus.NEW

    existing = session.query(Payable).filter(
        Payable.external_id == external_id,
        Payable.company_id == company_id,
    ).first()
    return DuplicateStatus.DUPLICATE if existing else DuplicateStatus.NEW
