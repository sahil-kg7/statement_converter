from __future__ import annotations

import re

from app.normalize.amount import parse_decimal_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.pipeline.models import Transaction


ROW_RE = re.compile(r"^\s*\d+\s+(\d{2}\s+\w{3}\s+\d{4})\s+(.*)$")
AMOUNT_RE = re.compile(r"[\d,]+\.\d{2}")
IGNORE_LINE_TOKENS = ("Opening Balance", "Account Summary", "End of Statement", "Statement Generated on")


class KotakSavingsPdfParser(PdfBankParser):
    bank = BankName.KOTAK
    statement_kind = StatementKind.SAVINGS

    def parse(self, extracted_text: str) -> list[Transaction]:
        lines = extracted_text.splitlines()
        header_line = self._find_header_line(lines)
        positions = self._column_positions(header_line)
        current: dict[str, object] | None = None
        transactions: list[Transaction] = []

        for line in self._iter_table_lines(lines, header_line):
            match = ROW_RE.match(line)
            if match is not None:
                current = self._append_completed(transactions, current)
                current = self._start_transaction(line, match, positions)
                continue

            self._append_continuation(current, line)

        if current is not None:
            transactions.append(self._build_transaction(current))

        return transactions

    @staticmethod
    def _find_header_line(lines: list[str]) -> str:
        header_line = next(
            (line for line in lines if "Date" in line and "Withdrawal (Dr.)" in line and "Deposit (Cr.)" in line),
            None,
        )
        if header_line is None:
            raise ValueError("Could not locate the Kotak savings transaction table")
        return header_line

    @staticmethod
    def _column_positions(header_line: str) -> tuple[int, int, int]:
        return (
            header_line.index("Withdrawal (Dr.)"),
            header_line.index("Deposit (Cr.)"),
            header_line.index("Balance"),
        )

    @staticmethod
    def _iter_table_lines(lines: list[str], header_line: str):
        seen_header = False
        for line in lines:
            if not seen_header:
                seen_header = line == header_line
                continue

            stripped = line.strip()
            if not stripped or stripped == "\x0c":
                continue
            if any(token in stripped for token in IGNORE_LINE_TOKENS):
                if stripped in {"Account Summary", "End of Statement"}:
                    return
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

    def _start_transaction(
        self,
        line: str,
        match: re.Match[str],
        positions: tuple[int, int, int],
    ) -> dict[str, object]:
        withdrawal_start, deposit_start, balance_start = positions
        amount_tokens = list(AMOUNT_RE.finditer(line))
        if len(amount_tokens) < 2:
            raise ValueError(f"Could not parse Kotak savings row: {line!r}")

        transaction_token = amount_tokens[-2]
        description_end = transaction_token.start()
        return {
            "date": match.group(1),
            "description_parts": [line[match.start(2):description_end].strip()],
            "withdrawal": line[withdrawal_start:deposit_start].strip(),
            "deposit": line[deposit_start:balance_start].strip(),
        }

    @staticmethod
    def _append_continuation(
        current: dict[str, object] | None,
        line: str,
    ) -> None:
        if current is None:
            return
        description_continuation = line.strip()
        if description_continuation:
            current["description_parts"].append(description_continuation)

    def _build_transaction(self, raw_transaction: dict[str, object]) -> Transaction:
        description_parts = raw_transaction["description_parts"]
        assert isinstance(description_parts, list)
        description = normalize_description(" ".join(part for part in description_parts if part and part != "-"))
        withdrawal = parse_decimal_amount(str(raw_transaction["withdrawal"])) or parse_decimal_amount("0")
        deposit = parse_decimal_amount(str(raw_transaction["deposit"])) or parse_decimal_amount("0")
        amount = deposit if deposit > 0 else -withdrawal

        return Transaction(
            transaction_date=normalize_transaction_date(str(raw_transaction["date"])),
            description=description,
            amount=amount,
        )
