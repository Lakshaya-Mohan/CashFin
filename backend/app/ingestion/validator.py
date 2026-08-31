"""
Validator — Stage 4

Responsibility: Validate normalized records and return structured errors.
Does NOT raise exceptions. Always returns a list of ValidationError objects.
The pipeline continues processing other rows when one row fails.
"""
from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.schemas.ingestion import NormalizedExpense, NormalizedInvoice, NormalizedTransaction, ValidationError

# Sanity bounds for financial amounts
MIN_AMOUNT = Decimal("0.01")
MAX_AMOUNT = Decimal("999_999_999.99")

# Date sanity window
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)


def validate_transaction(
    txn: NormalizedTransaction,
    row_number: int,
) -> List[ValidationError]:
    """
    Validate a NormalizedTransaction.
    Returns a list of ValidationError. Empty list = valid.
    """
    errors: List[ValidationError] = []

    # --- Amount ---
    if txn.amount < MIN_AMOUNT:
        errors.append(ValidationError(
            row_number=row_number,
            field="amount",
            error_message=f"Amount must be >= {MIN_AMOUNT}. Got: {txn.amount}",
            original_value=str(txn.amount),
        ))
    if txn.amount > MAX_AMOUNT:
        errors.append(ValidationError(
            row_number=row_number,
            field="amount",
            error_message=f"Amount {txn.amount} exceeds maximum allowed {MAX_AMOUNT}.",
            original_value=str(txn.amount),
        ))

    # --- Date ---
    if not (MIN_DATE <= txn.transaction_date <= MAX_DATE):
        errors.append(ValidationError(
            row_number=row_number,
            field="transaction_date",
            error_message=f"Date {txn.transaction_date} is outside the allowed range "
                          f"({MIN_DATE} to {MAX_DATE}).",
            original_value=str(txn.transaction_date),
        ))

    # --- Description ---
    if not txn.description or not txn.description.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="description",
            error_message="Description is empty. This record will be ingested but may "
                          "require manual review.",
            original_value=txn.description,
        ))

    return errors


def validate_invoice(
    invoice: NormalizedInvoice,
    row_number: int,
) -> List[ValidationError]:
    """
    Validate a NormalizedInvoice.
    Returns a list of ValidationError. Empty list = valid.
    """
    errors: List[ValidationError] = []

    if not invoice.invoice_number.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="invoice_number",
            error_message="Invoice number cannot be empty.",
            original_value=invoice.invoice_number,
        ))

    if not invoice.customer_name.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="customer_name",
            error_message="Customer name cannot be empty.",
            original_value=invoice.customer_name,
        ))

    if invoice.amount < MIN_AMOUNT:
        errors.append(ValidationError(
            row_number=row_number,
            field="amount",
            error_message=f"Invoice amount must be >= {MIN_AMOUNT}. Got: {invoice.amount}",
            original_value=str(invoice.amount),
        ))

    if invoice.due_date < invoice.invoice_date:
        errors.append(ValidationError(
            row_number=row_number,
            field="due_date",
            error_message=f"Due date ({invoice.due_date}) is before invoice date ({invoice.invoice_date}).",
            original_value=str(invoice.due_date),
        ))

    if not (Decimal("0") <= invoice.confidence <= Decimal("1")):
        errors.append(ValidationError(
            row_number=row_number,
            field="confidence",
            error_message=f"Confidence must be between 0 and 1. Got: {invoice.confidence}",
            original_value=str(invoice.confidence),
        ))

    return errors


def validate_expense(
    expense: NormalizedExpense,
    row_number: int,
) -> List[ValidationError]:
    """
    Validate a NormalizedExpense.
    Returns a list of ValidationError. Empty list = valid.
    """
    errors: List[ValidationError] = []

    if not expense.vendor_name.strip():
        errors.append(ValidationError(
            row_number=row_number,
            field="vendor_name",
            error_message="Vendor name cannot be empty.",
            original_value=expense.vendor_name,
        ))

    if expense.amount < MIN_AMOUNT:
        errors.append(ValidationError(
            row_number=row_number,
            field="amount",
            error_message=f"Expense amount must be >= {MIN_AMOUNT}. Got: {expense.amount}",
            original_value=str(expense.amount),
        ))

    if expense.is_future_obligation and expense.due_date is None:
        errors.append(ValidationError(
            row_number=row_number,
            field="due_date",
            error_message="due_date is required when is_future_obligation=True.",
            original_value=None,
        ))

    return errors
