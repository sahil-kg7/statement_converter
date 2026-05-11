from __future__ import annotations

import re
from datetime import datetime

import dateparser


DATE_PREFIX_PATTERNS = (
    re.compile(r"^\d{2}[-/]\d{2}[-/]\d{4}"),
    re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}"),
    re.compile(r"^\d{2}\s+[A-Za-z]{3}\s+\d{4}"),
)


def _extract_date_prefix(value: str) -> str:
    for pattern in DATE_PREFIX_PATTERNS:
        match = pattern.match(value)
        if match is not None:
            return match.group(0)
    return value


def normalize_transaction_date(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValueError("Transaction date is empty")

    primary_token = _extract_date_prefix(value)
    parsed = dateparser.parse(
        primary_token,
        settings={
            "DATE_ORDER": "DMY",
            "PREFER_DAY_OF_MONTH": "first",
        },
    )
    if parsed is None:
        raise ValueError(f"Could not parse date: {raw_value!r}")

    return parsed.strftime("%d-%m-%Y")


def normalize_statement_timestamp(raw_value: str) -> datetime:
    parsed = dateparser.parse(raw_value, settings={"DATE_ORDER": "DMY"})
    if parsed is None:
        raise ValueError(f"Could not parse statement timestamp: {raw_value!r}")
    return parsed
