from __future__ import annotations

import re

from app.normalize.amount import parse_decimal_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.pipeline.models import Transaction


ROW_RE = re.compile(
    r"^\s*(\d{2}/\d{2}/\d{4})\s+(.*?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$"
)
STOP_TOKENS = ("SUMMARY", "RD ACCOUNT SUMMARY", "Details of RD Interest", "*** End of Statement ***")
SKIP_PREFIXES = (
    "Page ",
    "Sahil Khanna",
    "Customer ID",
    "Account Number",
    "Joint Holders",
    "Account Type",
    "Statement From",
    "Currency",
    "Nomination",
    "Opening Balance",
    "Limit",
)


class HdfcSavingsPdfParser(PdfBankParser):
    bank = BankName.HDFC
    statement_kind = StatementKind.SAVINGS

    def parse(self, extracted_text: str) -> list[Transaction]:
        lines = extracted_text.splitlines()
        header_line = self._find_header_line(lines)
        current: dict[str, object] | None = None
        transactions: list[Transaction] = []

        for line in self._iter_table_lines(lines, header_line):
            match = ROW_RE.match(line)
            if match is not None:
                current = self._append_completed(transactions, current)
                current = self._start_transaction(match)
                continue

            self._append_continuation(current, line)

        if current is not None:
            transactions.append(self._build_transaction(current))

        return transactions

    @staticmethod
    def _find_header_line(lines: list[str]) -> str:
        header_line = next(
            (line for line in lines if "Txn Date" in line and "Withdrawals" in line and "Deposits" in line),
            None,
        )
        if header_line is None:
            raise ValueError("Could not locate the HDFC savings transaction table")
        return header_line

    @staticmethod
    def _iter_table_lines(lines: list[str], header_line: str):
        seen_header = False
        for line in lines:
            if not seen_header:
                seen_header = line == header_line
                continue

            stripped = line.strip()
            if any(token in stripped for token in STOP_TOKENS):
                return
            if not stripped or stripped == "\x0c" or stripped.startswith(SKIP_PREFIXES):
                continue
            yield line

    def _append_completed(
        self,
        transactions: list[Transaction],
        current: dict[str, object] | None,
    ) -> dict[str, object] | None:
        if current is not None:
            transactions.append(self._build_transaction(current))
        return None

    @staticmethod
    def _start_transaction(match: re.Match[str]) -> dict[str, object]:
        return {
            "date": match.group(1),
            "description_parts": [match.group(2).strip()],
            "withdrawal": match.group(3),
            "deposit": match.group(4),
        }

    @staticmethod
    def _append_continuation(current: dict[str, object] | None, line: str) -> None:
        if current is None:
            return
        continuation = line.strip()
        if continuation:
            current["description_parts"].append(continuation)

    def _build_transaction(self, raw_transaction: dict[str, object]) -> Transaction:
        description_parts = raw_transaction["description_parts"]
        assert isinstance(description_parts, list)
        withdrawal = parse_decimal_amount(str(raw_transaction["withdrawal"])) or parse_decimal_amount("0")
        deposit = parse_decimal_amount(str(raw_transaction["deposit"])) or parse_decimal_amount("0")
        amount = deposit if deposit > 0 else -withdrawal

        return Transaction(
            transaction_date=normalize_transaction_date(str(raw_transaction["date"])),
            description=normalize_description(" ".join(part for part in description_parts if part)),
            amount=amount,
        )
