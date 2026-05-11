from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.csv_adapters.base import CsvParseContext
from app.csv_adapters.generic import GenericCsvParser


def test_generic_csv_parser_handles_split_debit_credit_columns() -> None:
    raw_text = """Ignored preamble row
Date,Description,Debit,Credit,Balance
01/04/2026,Salary,,1200.00,2200.00
02/04/2026,Coffee,50.00,,2150.00
"""
    parser = GenericCsvParser()

    transactions = parser.parse(raw_text, CsvParseContext(source_path=Path("split.csv")))

    assert [tx.transaction_date for tx in transactions] == ["01-04-2026", "02-04-2026"]
    assert [tx.amount for tx in transactions] == [Decimal("1200.00"), Decimal("-50.00")]


def test_generic_csv_parser_handles_amount_plus_type_columns() -> None:
    raw_text = """Metadata
Txn Date,Narration,Amount,Dr/Cr
03-Apr-2026,Refund,200.00,CR
04-Apr-2026,Subscription,99.50,DR
"""
    parser = GenericCsvParser()

    transactions = parser.parse(raw_text, CsvParseContext(source_path=Path("typed.csv")))

    assert [tx.description for tx in transactions] == ["Refund", "Subscription"]
    assert [tx.amount for tx in transactions] == [Decimal("200.00"), Decimal("-99.50")]
