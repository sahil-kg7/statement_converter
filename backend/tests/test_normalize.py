from __future__ import annotations

from decimal import Decimal

from app.normalize.amount import clean_amount_text, format_signed_amount, signed_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description


def test_normalize_transaction_date_accepts_datetime_like_values() -> None:
    assert normalize_transaction_date("30-11-2025 19:28:51") == "30-11-2025 19:28"
    assert normalize_transaction_date("03-Apr-2026") == "03-04-2026"
    assert normalize_transaction_date("01 Apr 2026") == "01-04-2026"


def test_amount_helpers_strip_bank_specific_prefixes() -> None:
    assert clean_amount_text('="45,000.00"') == "45000.00"
    assert clean_amount_text("Rs.16,567.49") == "16567.49"
    assert clean_amount_text("C 17,452.00") == "17452.00"
    assert clean_amount_text("+ C 18,838.00") == "+18838.00"
    assert signed_amount(debit="1,000.00", credit=None) == Decimal("-1000.00")
    assert signed_amount(debit=None, credit='="2,500.00"') == Decimal("2500.00")


def test_format_and_description_normalization() -> None:
    assert normalize_description("  test   merchant  name ") == "test merchant name"
    assert format_signed_amount(Decimal("1200")) == "+1200.00"
    assert format_signed_amount(Decimal("-500")) == "-500.00"
