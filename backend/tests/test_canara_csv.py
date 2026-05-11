from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.csv_adapters.base import CsvParseContext
from app.csv_adapters.canara_savings import CanaraSavingsCsvParser


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = WORKSPACE_ROOT / "canara dec may.CSV"


def test_canara_csv_parser_reads_real_sample() -> None:
    raw_text = SAMPLE_PATH.read_text(encoding="utf-8")
    parser = CanaraSavingsCsvParser()

    assert parser.matches(raw_text) is True

    transactions = parser.parse(raw_text, CsvParseContext(source_path=SAMPLE_PATH))

    assert len(transactions) > 50
    assert transactions[0].transaction_date == "30-11-2025"
    assert transactions[0].amount == Decimal("45000.00")
    assert transactions[0].description.startswith("MOB-IMPS-CR/SAHIL KHAN/KMB")

    assert transactions[1].transaction_date == "30-11-2025"
    assert transactions[1].amount == Decimal("-42500.00")
    assert transactions[1].description.startswith("UPI/DR/570011533926/PAVULURI")

    assert any(tx.amount == Decimal("-10000.00") for tx in transactions)
    assert any(tx.amount == Decimal("2500.00") for tx in transactions)
