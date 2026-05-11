from __future__ import annotations

import csv
from io import StringIO
from typing import Iterable

from app.csv_adapters.base import CsvBankParser, CsvParseContext
from app.filters import dedupe_transactions, should_skip_row
from app.normalize.amount import parse_decimal_amount, signed_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.pipeline.models import Transaction


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("txn date", "transaction date", "date", "posted date"),
    "description": ("description", "narration", "particulars", "remarks"),
    "debit": ("debit", "withdrawal", "dr"),
    "credit": ("credit", "deposit", "cr"),
    "amount": ("amount",),
    "balance": ("balance",),
    "type": ("type", "dr/cr", "cr/dr"),
}


def _normalize_header(header: str) -> str:
    return " ".join(header.strip().lower().replace("_", " ").split())


def _pick_header_line(lines: list[str], dialect: csv.Dialect) -> int:
    best_index = -1
    best_score = -1

    for index, line in enumerate(lines[:25]):
        if not line.strip():
            continue
        parsed = next(csv.reader([line], dialect=dialect))
        headers = [_normalize_header(value) for value in parsed]
        score = 0
        for aliases in HEADER_ALIASES.values():
            if any(header in aliases for header in headers):
                score += 1
        if score > best_score:
            best_score = score
            best_index = index

    if best_index < 0 or best_score < 2:
        raise ValueError("Could not locate a recognizable CSV header row")
    return best_index


def _resolve_mapping(fieldnames: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for fieldname in fieldnames:
        normalized = _normalize_header(fieldname)
        for canonical, aliases in HEADER_ALIASES.items():
            if normalized in aliases and canonical not in mapping:
                mapping[canonical] = fieldname
                break
    if "date" not in mapping or "description" not in mapping:
        raise ValueError(f"Could not map required headers from: {fieldnames!r}")
    if "amount" not in mapping and not ({"debit", "credit"} & mapping.keys()):
        raise ValueError(f"Could not map any amount headers from: {fieldnames!r}")
    return mapping


def _iter_rows(raw_text: str) -> tuple[csv.Dialect, csv.DictReader]:
    sample = raw_text[:4096]
    lines = raw_text.splitlines()
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        header_probe = next((line for line in lines if any(symbol in line for symbol in [",", ";", "\t", "|"])), ",")
        delimiter = max((",", ";", "\t", "|"), key=header_probe.count)
        dialect = type(
            "FallbackDialect",
            (csv.Dialect,),
            {
                "delimiter": delimiter,
                "quotechar": '"',
                "doublequote": True,
                "skipinitialspace": False,
                "lineterminator": "\n",
                "quoting": csv.QUOTE_MINIMAL,
            },
        )

    header_index = _pick_header_line(lines, dialect)
    body = "\n".join(lines[header_index:])
    reader = csv.DictReader(StringIO(body), dialect=dialect)
    return dialect, reader


def _signed_amount_from_row(row: dict[str, str], mapping: dict[str, str]) -> object:
    if "credit" in mapping or "debit" in mapping:
        return signed_amount(
            debit=row.get(mapping.get("debit", ""), ""),
            credit=row.get(mapping.get("credit", ""), ""),
        )

    amount_value = parse_decimal_amount(row.get(mapping["amount"], ""))
    if amount_value is None:
        raise ValueError("Amount is empty")

    indicator_key = mapping.get("type")
    indicator = row.get(indicator_key, "") if indicator_key else ""
    indicator_normalized = indicator.strip().lower()
    if indicator_normalized in {"dr", "debit"}:
        return -amount_value
    if indicator_normalized in {"cr", "credit"}:
        return amount_value
    return amount_value


class GenericCsvParser(CsvBankParser):
    def matches(self, raw_text: str) -> bool:
        return True

    def parse(self, raw_text: str, context: CsvParseContext) -> list[Transaction]:
        _ = context
        _, reader = _iter_rows(raw_text)
        fieldnames = reader.fieldnames or []
        mapping = _resolve_mapping(fieldnames)

        transactions: list[Transaction] = []
        for row in reader:
            description = normalize_description(row.get(mapping["description"], ""))
            debit = row.get(mapping.get("debit", ""), "")
            credit = row.get(mapping.get("credit", ""), "")
            if should_skip_row(description, debit, credit):
                if "amount" not in mapping:
                    continue
                if not row.get(mapping["amount"], "").strip():
                    continue

            transactions.append(
                Transaction(
                    transaction_date=normalize_transaction_date(row[mapping["date"]]),
                    description=description,
                    amount=_signed_amount_from_row(row, mapping),
                )
            )
            if len(transactions) > 50_000:
                raise ValueError("CSV row count exceeds the configured limit")

        return dedupe_transactions(transactions)
