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


def test_hdfc_savings_v2_pdf_parses_new_format() -> None:
    transactions = _convert("hdfc 1 march to 19 june.pdf")

    assert len(transactions) == 28

    assert transactions[0].transaction_date == "01-03-2026"
    assert transactions[0].amount == Decimal("60000.00")
    assert "IMPS" in transactions[0].description

    assert transactions[2].amount == Decimal("-3550.52")
    assert "POS" in transactions[2].description
    assert "NIVA" in transactions[2].description

    assert transactions[4].amount == Decimal("-75991.44")
    assert "BILLPAY" in transactions[4].description

    interest_tx = [tx for tx in transactions if "INTEREST" in tx.description]
    assert len(interest_tx) == 1
    assert interest_tx[0].amount == Decimal("462.00")
    assert interest_tx[0].transaction_date == "01-04-2026"

    assert transactions[-1].amount == Decimal("-5000.00")
    assert "RD INSTALLMENT" in transactions[-1].description
    assert "JUN" in transactions[-1].description


def test_kotak_savings_v2_pdf_parses_signed_amounts() -> None:
    transactions = _convert("kotak 1 march to 20 june.pdf")

    assert len(transactions) == 40
    # Transaction 1: debit (negative) with time
    assert transactions[0].transaction_date == "12-06-2026 08:33"
    assert transactions[0].amount == Decimal("-10000.00")
    assert "SentIMPS616308085904Sahil" in transactions[0].description
    # Transaction 8: salary credit (positive) with time
    assert transactions[7].transaction_date == "01-06-2026 00:41"
    assert transactions[7].amount == Decimal("227766.00")
    assert "SALARY" in transactions[7].description
    # Transaction 12: LEOFORCE credit
    assert transactions[11].amount == Decimal("5587.00")
    assert "LEOFORCE" in transactions[11].description
    # Transaction 16: UPI debit to Malabar Gold
    assert transactions[15].amount == Decimal("-99000.00")
    assert "MALABAR GOLD" in transactions[15].description
    # Transaction 17: reversal credit on same page 2
    assert transactions[16].amount == Decimal("99000.00")
    assert "REV-UPI" in transactions[16].description
    # Last transaction (40): salary with time
    assert transactions[-1].transaction_date == "01-03-2026 00:55"
    assert transactions[-1].amount == Decimal("115555.00")
    # Verify all transactions have time in date and no time in descriptions
    for tx in transactions:
        assert " " in tx.transaction_date, f"Missing time in tx date: {tx.transaction_date}"
        assert "AM" not in tx.description.upper(), f"AM found in description: {tx.description}"
        assert "PM" not in tx.description.upper(), f"PM found in description: {tx.description}"
