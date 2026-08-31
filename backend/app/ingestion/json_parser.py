"""
JSON Parser — Stage 4

Responsibility: Read invoice and expense JSON files into raw Python dicts.
Does NOT normalize or validate. Pure I/O parsing.
"""
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def parse_json_file(file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse a JSON file containing a list of records.

    :param file_path: Path to a JSON file containing a list ([...]).
    :return: (records, parse_errors)
    """
    path = Path(file_path)
    if not path.exists():
        return [], [f"File not found: {file_path}"]

    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return [], [f"JSON parse error: {e}"]
    except Exception as e:
        return [], [f"Cannot read file: {e}"]

    if not isinstance(data, list):
        return [], ["JSON file must contain a top-level list ([...])."]

    return data, []


def parse_json_string(json_content: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parse JSON content from a string (useful for testing).

    :return: (records, parse_errors)
    """
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        return [], [f"JSON parse error: {e}"]

    if not isinstance(data, list):
        return [], ["JSON content must be a top-level list ([...])."]

    return data, []
