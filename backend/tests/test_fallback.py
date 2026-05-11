from __future__ import annotations

from decimal import Decimal

import pytest

from app.pipeline.errors import UnsupportedStatementError
from app.pipeline.fallback import redact_statement_text, run_fallback_chain


def test_generic_pdf_fallback_parses_line_based_statement_rows() -> None:
    extracted_text = """
    Some Bank Statement
    01-04-2026 UPI TO MERCHANT 1,250.00 19,000.00
    02-04-2026 NEFT FROM EMPLOYER 25,000.00 44,000.00
    03-04-2026 ATM CASH WITHDRAWAL 2,000.00 42,000.00
    """

    result = run_fallback_chain(
        b"pdf-bytes", extracted_text, layers_tried=["adapter:unmatched"]
    )

    assert [tx.transaction_date for tx in result.transactions] == [
        "01-04-2026",
        "02-04-2026",
        "03-04-2026",
    ]
    assert result.transactions[0].amount == Decimal("-1250.00")
    assert result.transactions[1].amount == Decimal("25000.00")
    assert result.layers_tried == ["adapter:unmatched", "generic_pdf"]


def test_redaction_masks_common_pii_tokens() -> None:
    redacted = redact_statement_text(
        "JOHN SAMPLE\nAccount Number\n123456789012\nCard 4111 1111 1111 1111\nABCD0123456\nABCDE1234F\nmail@example.com\n9876543210"
    )

    assert "<ACCT>" in redacted
    assert "<CARD>" in redacted
    assert "<IFSC>" in redacted
    assert "<PAN>" in redacted
    assert "<EMAIL>" in redacted
    assert "<PHONE>" in redacted


def test_fallback_raises_structured_error_when_no_layer_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.pipeline.fallback.settings.llm_provider", "none")

    with pytest.raises(UnsupportedStatementError) as error:
        run_fallback_chain(
            b"pdf-bytes",
            "Header only\nNo transaction rows",
            layers_tried=["adapter:unmatched"],
        )

    payload = error.value.to_payload()
    assert payload.error == "unsupported_statement"
    assert payload.hints["layers_tried"] == ["adapter:unmatched", "generic_pdf"]
