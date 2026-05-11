from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.pipeline.models import Transaction


class BankName(StrEnum):
    HDFC = "hdfc"
    KOTAK = "kotak"


class StatementKind(StrEnum):
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"


@dataclass(frozen=True)
class PdfDetectionResult:
    bank: BankName
    statement_kind: StatementKind


class PdfBankParser(Protocol):
    bank: BankName
    statement_kind: StatementKind

    def parse(self, extracted_text: str) -> list[Transaction]: ...
