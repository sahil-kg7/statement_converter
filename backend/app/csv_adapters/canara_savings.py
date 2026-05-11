from __future__ import annotations

import csv
from io import StringIO

from app.csv_adapters.base import CsvBankParser, CsvParseContext
from app.filters import dedupe_transactions, should_skip_row
from app.normalize.amount import signed_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.pipeline.models import Transaction


CANARA_HEADER = [
    "Txn Date",
    "Value Date",
    "Cheque No.",
    "Description",
    "Branch Code",
    "Debit",
    "Credit",
    "Balance",
    "",
]


def _strip_excel_escape(value: str | None) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if cleaned.startswith('="') and cleaned.endswith('"'):
        return cleaned[2:-1]
    return cleaned.strip('"')


def _find_header_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if line.strip().startswith("Txn Date,Value Date,Cheque No.,Description,Branch Code,Debit,Credit,Balance,"):
            return index
    raise ValueError("Could not locate Canara CSV header")


class CanaraSavingsCsvParser(CsvBankParser):
    def matches(self, raw_text: str) -> bool:
        return (
            "Current & Saving Account Statement" in raw_text
            and "Txn Date,Value Date,Cheque No.,Description,Branch Code,Debit,Credit,Balance," in raw_text
            and "CNRB" in raw_text
        )

    def parse(self, raw_text: str, context: CsvParseContext) -> list[Transaction]:
        _ = context
        lines = raw_text.splitlines()
        header_index = _find_header_index(lines)
        body = "\n".join(lines[header_index:])

        reader = csv.DictReader(StringIO(body))
        expected_header = reader.fieldnames
        if expected_header != CANARA_HEADER:
            raise ValueError(f"Unexpected Canara header: {expected_header!r}")

        transactions: list[Transaction] = []
        for row in reader:
            description = normalize_description(_strip_excel_escape(row["Description"]))
            debit = _strip_excel_escape(row["Debit"])
            credit = _strip_excel_escape(row["Credit"])
            if should_skip_row(description, debit, credit):
                continue

            transaction = Transaction(
                transaction_date=normalize_transaction_date(_strip_excel_escape(row["Txn Date"])),
                description=description,
                amount=signed_amount(debit=debit, credit=credit),
            )
            transactions.append(transaction)

        return dedupe_transactions(transactions)
