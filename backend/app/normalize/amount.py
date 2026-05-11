from __future__ import annotations

from decimal import Decimal


KNOWN_PREFIXES = ("Rs.", "INR", "₹", "C")


def clean_amount_text(raw_value: str | None) -> str:
    if raw_value is None:
        return ""

    value = raw_value.strip().strip('"').strip()
    if value.startswith("="):
        value = value[1:].strip().strip('"').strip()

    sign = ""
    if value.startswith(("+", "-")):
        sign = value[0]
        value = value[1:].strip()

    for prefix in KNOWN_PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix) :].strip()

    return f"{sign}{value.replace(',', '')}"


def parse_decimal_amount(raw_value: str | None) -> Decimal | None:
    cleaned = clean_amount_text(raw_value)
    if not cleaned:
        return None
    return Decimal(cleaned)


def signed_amount(debit: str | None = None, credit: str | None = None) -> Decimal:
    debit_amount = parse_decimal_amount(debit)
    credit_amount = parse_decimal_amount(credit)

    if debit_amount and credit_amount:
        raise ValueError("Both debit and credit are populated")
    if debit_amount is None and credit_amount is None:
        raise ValueError("Neither debit nor credit is populated")
    if credit_amount is not None:
        return credit_amount
    assert debit_amount is not None
    return -debit_amount


def format_signed_amount(amount: Decimal) -> str:
    prefix = "+" if amount >= 0 else "-"
    absolute = abs(amount)
    return f"{prefix}{absolute:.2f}"
