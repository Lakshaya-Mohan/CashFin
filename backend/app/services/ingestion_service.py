"""
Ingestion Service — Stage 4

Responsibility: Coordinate the full ingestion pipeline.
parse → normalize → validate → dedup → persist

Handles transactions (CSV), invoices (JSON), expenses (JSON), and receipts (Image).
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import date

from sqlalchemy.orm import Session

from app.ingestion.csv_parser import parse_csv_file
from app.ingestion.json_parser import parse_json_file
from app.ingestion.normalizer import (
    normalize_csv_row,
    normalize_expense,
    normalize_invoice,
)
from app.ingestion.validator import (
    validate_expense,
    validate_invoice,
    validate_transaction,
)
from app.ingestion.duplicate_detector import (
    DuplicateStatus,
    check_expense_duplicate,
    check_invoice_duplicate,
    check_transaction_duplicate,
    compute_transaction_fingerprint,
)
from app.ingestion.ocr_extractor import extract_from_image
from app.models.counterparty import Counterparty
from app.models.payable import Payable
from app.models.receivable import Receivable
from app.models.transaction import Transaction
from app.schemas.ingestion import (
    ExtractionStatus,
    IngestionResult,
    NormalizedExpense,
    NormalizedInvoice,
    NormalizedTransaction,
    RecordResult,
    ValidationError,
)


logger = logging.getLogger(__name__)


def ingest_bank_csv(
    file_path: str,
    company_id: int,
    account_id: int,
    session: Session,
) -> IngestionResult:
    """Ingest a bank statement CSV."""
    raw_rows, parse_errors = parse_csv_file(file_path)

    result = IngestionResult(
        total_records=len(raw_rows),
        inserted_records=0,
        duplicate_records=0,
        possible_duplicates=0,
        failed_records=0,
        errors=[
            ValidationError(row_number=0, field="file", error_message=e)
            for e in parse_errors
        ],
    )

    if not raw_rows:
        return result

    for row in raw_rows:
        row_number = int(row.get("_row_number", 0))
        rec_result = RecordResult(row_number=row_number)
        result.record_results.append(rec_result)

        try:
            normalized: NormalizedTransaction = normalize_csv_row(row, source_file=file_path)
        except ValueError as e:
            result.failed_records += 1
            rec_result.validation_errors.append(
                ValidationError(row_number=row_number, field="row", error_message=str(e))
            )
            continue

        # Fingerprint requires account_id
        fingerprint = compute_transaction_fingerprint(
            account_id=account_id,
            transaction_date=normalized.transaction_date,
            amount=normalized.amount,
            description=normalized.description,
            transaction_type=normalized.transaction_type.value,
        )
        normalized.fingerprint = fingerprint

        # Validate
        validation_errors = validate_transaction(normalized, row_number)
        if validation_errors:
            # We treat validation errors as failures for now, unless we want to ingest anyway (e.g. empty description is just a warning).
            # The validator returns an error for empty description, let's treat it as a warning if we want, but for deterministic behavior, let's fail it or log it.
            # Actually, the prompt says "The ingestion process must NOT crash... return structured results... do NOT automatically insert questionable financial records"
            # But the validator currently adds a ValidationError for empty desc. Let's consider ANY validation error a failure.
            # Wait, the validator says "This record will be ingested but may require manual review" for empty description.
            # Let's filter out warnings. For simplicity, we just fail it if there are ANY validation errors from validate_transaction.
            pass
        
        # Actually, let's just fail if validation_errors exist, EXCEPT for empty description which we might want to allow. Let's just fail all.
        if any("Description is empty" not in e.error_message for e in validation_errors):
            result.failed_records += 1
            rec_result.validation_errors.extend(validation_errors)
            result.errors.extend(validation_errors)
            continue

        if validation_errors:
             # Just warnings
             rec_result.validation_errors.extend(validation_errors)
             result.errors.extend(validation_errors)

        # Dedup
        dup_status = check_transaction_duplicate(
            session,
            external_id=normalized.external_id,
            fingerprint=normalized.fingerprint,
        )
        rec_result.duplicate_status = dup_status

        if dup_status == DuplicateStatus.DUPLICATE:
            result.duplicate_records += 1
            continue
        elif dup_status == DuplicateStatus.POSSIBLE_DUPLICATE:
            # We flag it, but do we insert? The problem says "classify records as POSSIBLE_DUPLICATE".
            # "A receipt imported twice should be identified as a duplicate."
            # "Do not automatically delete duplicates." -> The prompt says:
            # "Second import of same file: 100 records -> 0 duplicate transactions inserted"
            # We DO NOT insert.
            result.possible_duplicates += 1
            continue
            
        # Persist
        txn_model = Transaction(
            account_id=account_id,
            transaction_date=normalized.transaction_date,
            amount=normalized.amount,
            transaction_type=normalized.transaction_type.value,
            description=normalized.description,
            category=normalized.category,
            source=normalized.source,
            external_id=normalized.external_id,
            fingerprint=normalized.fingerprint,
        )
        session.add(txn_model)
        session.flush()
        rec_result.inserted = True
        result.inserted_records += 1
        
    session.commit()
    return result


def _get_or_create_counterparty(
    session: Session,
    company_id: int,
    name: str,
    counterparty_type: str = "CUSTOMER",
) -> Counterparty:
    existing = session.query(Counterparty).filter(
        Counterparty.company_id == company_id,
        Counterparty.name == name,
    ).first()
    if existing:
        return existing

    cp = Counterparty(
        company_id=company_id,
        name=name,
        counterparty_type=counterparty_type,
    )
    session.add(cp)
    session.flush() # get ID
    return cp


def ingest_invoices_json(
    file_path: str,
    company_id: int,
    session: Session,
) -> IngestionResult:
    """Ingest invoices from a JSON file."""
    raw_records, parse_errors = parse_json_file(file_path)

    result = IngestionResult(
        total_records=len(raw_records),
        inserted_records=0,
        duplicate_records=0,
        possible_duplicates=0,
        failed_records=0,
        errors=[
            ValidationError(row_number=0, field="file", error_message=e)
            for e in parse_errors
        ],
    )

    for i, raw in enumerate(raw_records, start=1):
        rec_result = RecordResult(row_number=i)
        result.record_results.append(rec_result)

        try:
            normalized: NormalizedInvoice = normalize_invoice(raw)
        except ValueError as e:
            result.failed_records += 1
            rec_result.validation_errors.append(
                ValidationError(row_number=i, field="row", error_message=str(e))
            )
            continue

        validation_errors = validate_invoice(normalized, i)
        if validation_errors:
            result.failed_records += 1
            rec_result.validation_errors.extend(validation_errors)
            result.errors.extend(validation_errors)
            continue

        dup_status = check_invoice_duplicate(
            session,
            invoice_number=normalized.invoice_number,
            company_id=company_id,
        )
        rec_result.duplicate_status = dup_status
        if dup_status != DuplicateStatus.NEW:
            result.duplicate_records += 1
            continue

        cp = _get_or_create_counterparty(session, company_id, normalized.customer_name, "CUSTOMER")

        rec = Receivable(
            company_id=company_id,
            counterparty_id=cp.id,
            amount=normalized.amount,
            expected_date=normalized.due_date,
            confidence=normalized.confidence,
            status="EXPECTED",
            description=normalized.description or f"Invoice {normalized.invoice_number}",
            external_id=normalized.invoice_number,
        )
        session.add(rec)
        session.flush()
        rec_result.inserted = True
        result.inserted_records += 1

    session.commit()
    return result


def ingest_expenses_json(
    file_path: str,
    company_id: int,
    account_id: int, # Needed if it's already paid and becomes a Transaction
    session: Session,
    as_of_date: Optional[date] = None,
) -> IngestionResult:
    """Ingest expenses from a JSON file."""
    raw_records, parse_errors = parse_json_file(file_path)

    result = IngestionResult(
        total_records=len(raw_records),
        inserted_records=0,
        duplicate_records=0,
        possible_duplicates=0,
        failed_records=0,
        errors=[
            ValidationError(row_number=0, field="file", error_message=e)
            for e in parse_errors
        ],
    )

    for i, raw in enumerate(raw_records, start=1):
        rec_result = RecordResult(row_number=i)
        result.record_results.append(rec_result)

        try:
            normalized: NormalizedExpense = normalize_expense(raw, as_of_date)
        except ValueError as e:
            result.failed_records += 1
            rec_result.validation_errors.append(
                ValidationError(row_number=i, field="row", error_message=str(e))
            )
            continue

        validation_errors = validate_expense(normalized, i)
        if validation_errors:
            result.failed_records += 1
            rec_result.validation_errors.extend(validation_errors)
            result.errors.extend(validation_errors)
            continue

        if normalized.is_future_obligation:
            # It's a Payable
            dup_status = check_expense_duplicate(session, normalized.external_id, company_id)
            rec_result.duplicate_status = dup_status
            if dup_status != DuplicateStatus.NEW:
                result.duplicate_records += 1
                continue
            
            cp = _get_or_create_counterparty(session, company_id, normalized.vendor_name, "SUPPLIER")
            pay = Payable(
                company_id=company_id,
                counterparty_id=cp.id,
                amount=normalized.amount,
                due_date=normalized.due_date,
                status="PENDING",
                description=normalized.description,
                external_id=normalized.external_id,
            )
            session.add(pay)
            session.flush()
        else:
            # It's a Transaction (Expense)
            fingerprint = compute_transaction_fingerprint(
                account_id=account_id,
                transaction_date=normalized.expense_date,
                amount=normalized.amount,
                description=normalized.description,
                transaction_type="EXPENSE",
            )
            dup_status = check_transaction_duplicate(session, normalized.external_id, fingerprint)
            rec_result.duplicate_status = dup_status
            if dup_status == DuplicateStatus.DUPLICATE:
                result.duplicate_records += 1
                continue
            elif dup_status == DuplicateStatus.POSSIBLE_DUPLICATE:
                result.possible_duplicates += 1
                continue
                
            txn = Transaction(
                account_id=account_id,
                transaction_date=normalized.expense_date,
                amount=normalized.amount,
                transaction_type="EXPENSE",
                description=normalized.description,
                category="Expense",
                source="expense_json",
                external_id=normalized.external_id,
                fingerprint=fingerprint,
            )
            session.add(txn)
            session.flush()

        rec_result.inserted = True
        result.inserted_records += 1

    session.commit()
    return result


def ingest_receipt_image(
    image_path: str,
    company_id: int,
    account_id: int,
    session: Session,
) -> IngestionResult:
    """Ingest a receipt image via OCR."""
    result = IngestionResult(
        total_records=1,
        inserted_records=0,
        duplicate_records=0,
        possible_duplicates=0,
        failed_records=0,
    )
    rec_result = RecordResult(row_number=1)
    result.record_results.append(rec_result)

    extracted = extract_from_image(image_path)
    
    if extracted.extraction_status in (ExtractionStatus.FAILED, ExtractionStatus.NEEDS_REVIEW):
        result.failed_records = 1
        for e in extracted.validation_errors:
            rec_result.validation_errors.append(
                ValidationError(row_number=1, field="ocr", error_message=e)
            )
            result.errors.append(ValidationError(row_number=1, field="ocr", error_message=e))
        return result

    # For receipt images, we assume they are already paid (Transactions), not future payables.
    # We create a Transaction.
    fingerprint = compute_transaction_fingerprint(
        account_id=account_id,
        transaction_date=extracted.receipt_date,
        amount=extracted.amount,
        description=extracted.vendor, # Use vendor as description for transaction
        transaction_type="EXPENSE",
    )
    
    dup_status = check_transaction_duplicate(session, extracted.receipt_number, fingerprint)
    rec_result.duplicate_status = dup_status
    if dup_status == DuplicateStatus.DUPLICATE:
        result.duplicate_records = 1
        return result
    elif dup_status == DuplicateStatus.POSSIBLE_DUPLICATE:
        result.possible_duplicates = 1
        return result
        
    txn = Transaction(
        account_id=account_id,
        transaction_date=extracted.receipt_date,
        amount=extracted.amount,
        transaction_type="EXPENSE",
        description=extracted.vendor,
        category="Receipt",
        source="receipt_ocr",
        external_id=extracted.receipt_number,
        fingerprint=fingerprint,
    )
    session.add(txn)
    session.commit()
    
    result.inserted_records = 1
    rec_result.inserted = True
    return result
