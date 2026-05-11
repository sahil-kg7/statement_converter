from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.pipeline.orchestrator import ConversionOrchestrator


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _convert(file_name: str):
    orchestrator = ConversionOrchestrator()
    payload = (WORKSPACE_ROOT / file_name).read_bytes()
    return orchestrator.convert(file_name, payload).transactions


def test_hdfc_savings_pdf_parses_expected_rows() -> None:
    transactions = _convert("HDFC_Apr_2026.pdf")

    assert len(transactions) == 7
    assert transactions[0].transaction_date == "06-04-2026"
    assert transactions[0].amount == Decimal("-18838.00")
    assert transactions[1].amount == Decimal("15000.00")
    assert any("RELIANCE JEWELS" in tx.description for tx in transactions)


def test_hdfc_credit_card_pdf_parses_payments_and_international_rows() -> None:
    transactions = _convert("HDFC_CC_Apr_2026.pdf")

    assert any(tx.amount == Decimal("18838.00") and "CREDIT CARD PAYMENT" in tx.description for tx in transactions)
    assert any(tx.amount == Decimal("-1016.96") and "[USD 10.80]" in tx.description for tx in transactions)
    assert any(tx.amount == Decimal("-2444.95") and "OFFUS EMI,PRIN" in tx.description for tx in transactions)


def test_kotak_savings_pdf_parses_transactions() -> None:
    transactions = _convert("Kotak_Apr_2026.pdf")

    assert len(transactions) == 9
    assert transactions[0].transaction_date == "01-04-2026"
    assert transactions[0].amount == Decimal("-30000.00")
    assert any("BILL PAID TO CREDIT CARD 2772" in tx.description for tx in transactions)


def test_kotak_credit_card_pdf_parses_payments_purchases_and_fees() -> None:
    transactions = _convert("Kotak_CC_Apr_2026.pdf")

    assert any(tx.amount == Decimal("5664.11") and "CCBILL-0000049383582" in tx.description for tx in transactions)
    assert any(tx.amount == Decimal("-942.82") and "BHARTI AIRTEL LTD" in tx.description for tx in transactions)
    assert any(tx.amount == Decimal("-900.00") and "LATE PAYMENT FEE" in tx.description for tx in transactions)
