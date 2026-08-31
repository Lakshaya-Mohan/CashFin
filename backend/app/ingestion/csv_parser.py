"""
CSV Parser — Stage 4

Responsibility: Read external CSV files and convert rows to raw Python dicts.
Does NOT normalize, validate, or persist. Pure I/O parsing.

Supports flexible column name aliasing to handle real-world bank statement
format variations without requiring the user to pre-process the file.
"""
import csv
import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Column alias mapping
# Keys are CashFin canonical names; values are accepted source variations.
# All comparisons are done case-insensitively with whitespace stripped.
# ---------------------------------------------------------------------------
COLUMN_ALIASES: Dict[str, List[str]] = {
    "transaction_date": [
        "date", "transaction date", "txn date", "value date",
        "posted date", "trans date", "booking date",
    ],
    "description": [
        "description", "narration", "details", "particulars",
        "remarks", "transaction details", "memo",
    ],
    "amount": [
        "amount", "transaction amount", "txn amount", "value",
    ],
    "transaction_type": [
        "type", "cr/dr", "debit/credit", "transaction type",
        "dr/cr", "txn type",
    ],
    "external_id": [
        "reference", "ref", "txn id", "transaction id",
        "chq./ref.no.", "reference no", "ref no", "utr",
    ],
}


def _build_column_map(headers: List[str]) -> Dict[str, str]:
    """
    Build a mapping from canonical names → actual CSV header names.

    :param headers: Raw CSV header strings.
    :return: Dict[canonical_name → actual_header].
    """
    normalized_headers = {h.strip().lower(): h for h in headers}
    column_map: Dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized_headers:
                column_map[canonical] = normalized_headers[alias]
                break

    return column_map


def parse_csv_file(
    file_path: str,
    column_map_override: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parse a bank statement CSV file into a list of raw row dicts.

    :param file_path: Absolute or relative path to the CSV file.
    :param column_map_override: Optional override mapping (canonical → actual header).
                                Use when the alias detection fails for an unusual format.
    :return: (rows, parse_errors)
             rows: list of dicts with canonical keys (may still have raw string values).
             parse_errors: list of human-readable error strings.
    """
    path = Path(file_path)
    if not path.exists():
        return [], [f"File not found: {file_path}"]

    parse_errors: List[str] = []
    rows: List[Dict[str, str]] = []

    try:
        content = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    except Exception as e:
        return [], [f"Cannot read file: {e}"]

    reader = csv.DictReader(io.StringIO(content))

    if reader.fieldnames is None:
        return [], ["CSV file is empty or has no headers."]

    column_map = column_map_override or _build_column_map(list(reader.fieldnames))

    # Require at minimum: date + amount (description and type optional per row)
    for required in ("transaction_date", "amount"):
        if required not in column_map:
            parse_errors.append(
                f"Required column '{required}' not found. "
                f"Available headers: {list(reader.fieldnames)}. "
                f"Expected aliases: {COLUMN_ALIASES[required]}"
            )

    if parse_errors:
        return [], parse_errors

    for row_number, raw_row in enumerate(reader, start=2):  # Row 1 = header
        normalized: Dict[str, str] = {"_row_number": str(row_number)}
        for canonical, actual_header in column_map.items():
            normalized[canonical] = (raw_row.get(actual_header) or "").strip()
        rows.append(normalized)

    return rows, parse_errors


def parse_csv_string(
    csv_content: str,
    column_map_override: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, str]], List[str]]:
    """
    Parse CSV content from a string (useful for testing).

    :param csv_content: Full CSV file content as a string.
    :return: (rows, parse_errors)
    """
    parse_errors: List[str] = []
    reader = csv.DictReader(io.StringIO(csv_content))

    if reader.fieldnames is None:
        return [], ["CSV content is empty or has no headers."]

    column_map = column_map_override or _build_column_map(list(reader.fieldnames))

    for required in ("transaction_date", "amount"):
        if required not in column_map:
            parse_errors.append(
                f"Required column '{required}' not found. "
                f"Available headers: {list(reader.fieldnames)}."
            )

    if parse_errors:
        return [], parse_errors

    rows: List[Dict[str, str]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        normalized: Dict[str, str] = {"_row_number": str(row_number)}
        for canonical, actual_header in column_map.items():
            normalized[canonical] = (raw_row.get(actual_header) or "").strip()
        rows.append(normalized)

    return rows, parse_errors
