from __future__ import annotations

import re

from app.normalize.amount import parse_decimal_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.pipeline.models import Transaction


ROW_RE = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s*\|\s*(\d{2}:\d{2})")


class HdfcCreditCardPdfParser(PdfBankParser):
    bank = BankName.HDFC
    statement_kind = StatementKind.CREDIT_CARD

    def parse(self, extracted_text: str) -> list[Transaction]:
        lines = extracted_text.splitlines()
        transactions: list[Transaction] = []
        current_section: str | None = None
        header_amount_start: int | None = None
        header_pi_start: int | None = None
        header_desc_start: int | None = None

        for line in lines:
            stripped = line.strip()
            section = self._section_transition(stripped)
            if section is not None:
                current_section = section
                header_amount_start, header_pi_start, header_desc_start = None, None, None
                continue

            if current_section and self._is_header_line(line):
                header_desc_start, header_amount_start, header_pi_start = self._header_positions(line)
                continue

            if self._should_stop(stripped):
                break

            if self._should_skip(stripped, current_section, header_desc_start, header_amount_start, header_pi_start):
                continue

            transaction = self._parse_row(line, header_desc_start, header_amount_start, header_pi_start)
            if transaction is not None:
                transactions.append(transaction)

        return transactions

    @staticmethod
    def _section_transition(stripped: str) -> str | None:
        if stripped in {"Domestic Transactions", "International Transactions"}:
            return stripped
        return None

    @staticmethod
    def _is_header_line(line: str) -> bool:
        return "DATE & TIME" in line and "TRANSACTION DESCRIPTION" in line and "AMOUNT" in line

    @staticmethod
    def _header_positions(line: str) -> tuple[int, int, int]:
        return (
            line.index("TRANSACTION DESCRIPTION"),
            line.index("AMOUNT"),
            line.index("PI"),
        )

    @staticmethod
    def _should_stop(stripped: str) -> bool:
        return stripped.startswith(("Rewards Program Points Summary", "GST Summary", "Important Information"))

    @staticmethod
    def _should_skip(
        stripped: str,
        current_section: str | None,
        header_desc_start: int | None,
        header_amount_start: int | None,
        header_pi_start: int | None,
    ) -> bool:
        return (
            not current_section
            or header_desc_start is None
            or header_amount_start is None
            or header_pi_start is None
            or not stripped
            or stripped in {"SAHIL KHANNA", "*Transaction time captured in IST Zone."}
        )

    def _parse_row(
        self,
        line: str,
        header_desc_start: int,
        header_amount_start: int,
        header_pi_start: int,
    ) -> Transaction | None:
        match = ROW_RE.match(line)
        if match is None:
            return None

        date_text = match.group(1)
        description_chunk = line[header_desc_start:header_amount_start].strip()
        amount_chunk = line[header_amount_start:header_pi_start].strip()
        if not description_chunk or not amount_chunk:
            return None

        amount_value = parse_decimal_amount(amount_chunk)
        if amount_value is None:
            return None

        description = self._normalize_description(description_chunk)
        is_positive = amount_chunk.startswith("+") or description_chunk.upper().startswith("CREDIT CARD PAYMENT")
        signed = amount_value if is_positive else -amount_value
        return Transaction(
            transaction_date=normalize_transaction_date(date_text),
            description=description,
            amount=signed,
        )

    @staticmethod
    def _normalize_description(description_chunk: str) -> str:
        fx_match = re.search(r"(USD\s+[\d,.]+)$", description_chunk)
        if fx_match:
            description_chunk = f"{description_chunk[:fx_match.start()].strip()} [{fx_match.group(1)}]"
        return normalize_description(description_chunk)
