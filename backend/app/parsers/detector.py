from __future__ import annotations

from app.parsers.base import BankName, PdfDetectionResult, StatementKind


def detect_pdf_statement(extracted_text: str) -> PdfDetectionResult | None:
    lower_text = extracted_text.lower()

    if "millennia credit card statement" in lower_text and "hdfc bank credit cards gstin" in lower_text:
        return PdfDetectionResult(BankName.HDFC, StatementKind.CREDIT_CARD)

    if "monthly statement for your pvr kotak platinum credit card" in lower_text:
        return PdfDetectionResult(BankName.KOTAK, StatementKind.CREDIT_CARD)

    if "savings account transactions" in lower_text and "account type savings" in lower_text:
        return PdfDetectionResult(BankName.KOTAK, StatementKind.SAVINGS)

    if "savings account details" in lower_text and "savings a/c - resident" in lower_text:
        return PdfDetectionResult(BankName.HDFC, StatementKind.SAVINGS)

    return None
