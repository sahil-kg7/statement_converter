from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_date: str = Field(pattern=r"^\d{2}-\d{2}-\d{4}( \d{2}:\d{2})?$")
    description: str = Field(min_length=1)
    amount: Decimal


class ConversionResult(BaseModel):
    transactions: list[Transaction]
    detected_bank: str | None = None
    statement_kind: str | None = None
    conversion_source: str = "adapter"
