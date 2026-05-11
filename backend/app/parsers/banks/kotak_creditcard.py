from __future__ import annotations

import re

from app.normalize.amount import parse_decimal_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.pipeline.models import Transaction


ROW_RE = re.compile(r"^\s*(\d{2}-\w{3}-\d{4})\s+")
AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})(?:\s+Cr)?$")


class KotakCreditCardPdfParser(PdfBankParser):
    bank = BankName.KOTAK
    statement_kind = StatementKind.CREDIT_CARD

    def parse(self, extracted_text: str) -> list[Transaction]:
        lines = extracted_text.splitlines()
        transactions: list[Transaction] = []
        current_section: str | None = None
        in_transaction_area = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Transactions Details from"):
                in_transaction_area = True
                continue
            if not in_transaction_area:
                continue

            if self._is_header_line(line):
                continue

            section = self._section_transition(stripped)
            if section is not None:
                current_section = section
                continue

            if self._should_skip(
                stripped,
                current_section,
            ):
                continue

            transaction = self._parse_row(
                line,
                current_section,
            )
            if transaction is not None:
                transactions.append(transaction)

        return transactions

    @staticmethod
    def _is_header_line(line: str) -> bool:
        return "Description Spends" in line and "Amount" in line and "Date" in line

    @staticmethod
    def _section_transition(stripped: str) -> str | None:
        if stripped in {
            "Payments and Other Credits",
            "Purchases made in this cycle - Primary Card X2772",
            "Other fees and charges",
        }:
            return stripped
        return None

    @staticmethod
    def _should_skip(
        stripped: str,
        current_section: str | None,
    ) -> bool:
        return (
            stripped.startswith(("Total Purchases", "Total Fees & Charges", "Need quick access?", "GST applicable"))
            or stripped in {"", "\x0c"}
            or current_section is None
            or stripped == "SAHIL KHANNA"
        )

    def _parse_row(
        self,
        line: str,
        current_section: str,
    ) -> Transaction | None:
        match = ROW_RE.match(line)
        if match is None:
            return None

        date_text = match.group(1)
        remainder = line[match.end() :].strip()
        amount_match = AMOUNT_RE.search(remainder)
        if amount_match is None:
            return None
        amount_text = amount_match.group(0)
        description = remainder[: amount_match.start()].strip()
        amount_match = AMOUNT_RE.search(amount_text)
        if not date_text or not description or amount_match is None:
            return None

        amount_value = parse_decimal_amount(amount_match.group(1))
        if amount_value is None:
            return None

        is_positive = "Cr" in amount_text or current_section == "Payments and Other Credits"
        signed = amount_value if is_positive else -amount_value
        return Transaction(
            transaction_date=normalize_transaction_date(date_text),
            description=normalize_description(description),
            amount=signed,
        )
