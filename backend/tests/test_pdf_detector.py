from __future__ import annotations

from pathlib import Path

from app.parsers.base import BankName, StatementKind
from app.parsers.detector import detect_pdf_statement
from app.parsers.text_extractor import extract_pdf_text


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def _extract(relative_name: str) -> str:
    payload = (WORKSPACE_ROOT / relative_name).read_bytes()
    return extract_pdf_text(payload).text


def test_hdfc_savings_detection() -> None:
    detection = detect_pdf_statement(_extract("HDFC_Apr_2026.pdf"))
    assert detection is not None
    assert detection.bank is BankName.HDFC
    assert detection.statement_kind is StatementKind.SAVINGS


def test_hdfc_savings_v2_detection() -> None:
    detection = detect_pdf_statement(_extract("hdfc 1 march to 19 june.pdf"))
    assert detection is not None
    assert detection.bank is BankName.HDFC
    assert detection.statement_kind is StatementKind.SAVINGS


def test_hdfc_credit_card_detection() -> None:
    detection = detect_pdf_statement(_extract("HDFC_CC_Apr_2026.pdf"))
    assert detection is not None
    assert detection.bank is BankName.HDFC
    assert detection.statement_kind is StatementKind.CREDIT_CARD


def test_kotak_savings_detection() -> None:
    detection = detect_pdf_statement(_extract("Kotak_Apr_2026.pdf"))
    assert detection is not None
    assert detection.bank is BankName.KOTAK
    assert detection.statement_kind is StatementKind.SAVINGS


def test_kotak_credit_card_detection() -> None:
    detection = detect_pdf_statement(_extract("Kotak_CC_Apr_2026.pdf"))
    assert detection is not None
    assert detection.bank is BankName.KOTAK
    assert detection.statement_kind is StatementKind.CREDIT_CARD
