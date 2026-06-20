from __future__ import annotations

import re

from app.normalize.amount import parse_decimal_amount
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.parsers.base import BankName, PdfBankParser, StatementKind
from app.pipeline.models import Transaction


ROW_RE = re.compile(r"^\s*\d+\s+(\d{2}\s+\w{3}\s+\d{4})\s+(.*)$")
AMOUNT_RE = re.compile(r"[+-]?[\d,]+\.\d{2}")
_TIME_PREFIX_RE = re.compile(r"^(\d{1,2}:\d{2}\s+(?:AM|PM))(\s+.*)?$", re.IGNORECASE)
IGNORE_LINE_TOKENS = (
    "Opening Balance",
    "Closing Balance",
    "Account Summary",
    "End of Statement",
)
_PAGE_SKIP_PREFIXES = ("Statement generated on", "Statement Generated on", "Account Statement")
_PAGE_SKIP_EXACT = ("SAHIL KHANNA",)


class KotakSavingsPdfParserV2(PdfBankParser):
    """Parser for Kotak savings PDFs with signed DEBIT/CREDIT(₹) column.

    Handles the newer statement format where amounts are already signed
    (negative = debit, positive = credit) in a single column, as opposed to
    the older format with separate unsigned Withdrawal/Deposit columns.
    Supports multi-page statements with repeated page headers.
    """

    bank = BankName.KOTAK
    statement_kind = StatementKind.SAVINGS

    def parse(self, extracted_text: str) -> list[Transaction]:
        lines = extracted_text.splitlines()
        self._find_header_line(lines)
        current: dict | None = None
        transactions: list[Transaction] = []
        self._pending_time: str | None = None

        for line in self._iter_table_lines(lines):
            match = ROW_RE.match(line)
            if match is not None:
                current = self._append_completed(transactions, current)
                current = self._start_transaction(line, match)
                continue

            line = self._strip_time_prefix(line)
            self._append_continuation(current, line)

        if current is not None:
            transactions.append(self._build_transaction(current, self._pending_time))

        return transactions

    @staticmethod
    def _find_header_line(lines: list[str]) -> str:
        for line in lines:
            if (
                "TRANSACTION DATE" in line
                and "DEBIT/CREDIT(₹)" in line
                and "BALANCE(₹)" in line
            ):
                return line
        raise ValueError("Could not locate the Kotak savings v2 transaction table")

    @staticmethod
    def _iter_table_lines(lines: list[str]):
        """Yield transaction data lines, skipping page-level headers and footers.

        Handles multi-page statements where each page repeats:
          - Account holder name (e.g. "SAHIL KHANNA")
          - "Account Statement ..."
          - The column header row
          - A footer line "Statement generated on ..." before the form feed
        """
        seen_header = False
        for line in lines:
            # Skip form feeds (page breaks embedded in raw line)
            if "\x0c" in line:
                continue

            stripped = line.strip()

            if not seen_header:
                if "TRANSACTION DATE" in line and "DEBIT/CREDIT(₹)" in line:
                    seen_header = True
                continue

            if not stripped:
                continue

            # Skip page-level header lines repeated on continuation pages
            if stripped.startswith(_PAGE_SKIP_PREFIXES):
                continue
            if stripped in _PAGE_SKIP_EXACT:
                continue

            # Stop at summary/footer markers
            if any(token in stripped for token in IGNORE_LINE_TOKENS):
                if stripped in {"Account Summary", "End of Statement"}:
                    return
                continue

            # Skip repeated column headers on page 2+
            if "TRANSACTION DATE" in line and "DEBIT/CREDIT(₹)" in line:
                continue

            yield line

    def _append_completed(
        self,
        transactions: list[Transaction],
        current: dict | None,
    ) -> dict | None:
        if current is not None:
            transactions.append(self._build_transaction(current, self._pending_time))
            self._pending_time = None
        return None

    @staticmethod
    def _start_transaction(
        line: str,
        match: re.Match,
    ) -> dict:
        """Extract date, description, and signed amount from a transaction row.

        Uses regex to find amount tokens (signed decimals) in the line.
        The second-to-last amount token is the DEBIT/CREDIT value;
        the last is the balance (ignored).
        Description is everything between the value date and the amount.
        """
        amount_tokens = list(AMOUNT_RE.finditer(line))
        if len(amount_tokens) < 1:
            raise ValueError(f"Could not parse Kotak savings v2 row: {line!r}")

        # The second-to-last amount token is the debit/credit amount
        amount_token = amount_tokens[-2] if len(amount_tokens) >= 2 else amount_tokens[-1]
        description_end = amount_token.start()

        # Description: text between value date end and the amount start
        # match.group(2) starts at value date; "DD Mon YYYY" is always 11 chars
        description_start = match.start(2) + 11
        description = line[description_start:description_end].strip()

        return {
            "date": match.group(1),
            "description_parts": [description],
            "amount_raw": amount_token.group(0),
        }

    @staticmethod
    def _append_continuation(
        current: dict | None,
        line: str,
    ) -> None:
        if current is None:
            return
        continuation = line.strip()
        if continuation:
            current["description_parts"].append(continuation)

    def _strip_time_prefix(self, line: str) -> str:
        stripped = line.strip()
        match = _TIME_PREFIX_RE.match(stripped)
        if match is not None:
            self._pending_time = self._convert_to_24h(match.group(1))
            remainder = match.group(2) or ""
            if remainder.strip():
                return remainder
            return ""
        return line

    @staticmethod
    def _convert_to_24h(time_str: str) -> str:
        match = re.match(r"^(\d{1,2}:\d{2})\s*(AM|PM)$", time_str.strip(), re.IGNORECASE)
        if match is None:
            return time_str
        time_part, meridiem = match.groups()
        if meridiem.upper() == "PM" and not time_part.startswith("12"):
            hours, minutes = time_part.split(":")
            hours = str(int(hours) + 12)
            time_part = f"{hours}:{minutes}"
        elif meridiem.upper() == "AM" and time_part.startswith("12"):
            time_part = f"00:{time_part.split(':')[1]}"
        return time_part

    def _build_transaction(self, raw: dict, pending_time: str | None = None) -> Transaction:
        parts = raw["description_parts"]
        description = normalize_description(" ".join(p for p in parts if p and p != "-"))
        amount_str = str(raw["amount_raw"])
        amount = parse_decimal_amount(amount_str)
        if amount is None:
            amount = parse_decimal_amount("0")

        date_str = str(raw["date"])
        if pending_time:
            date_str = f"{date_str} {pending_time}"

        return Transaction(
            transaction_date=normalize_transaction_date(date_str),
            description=description,
            amount=amount,
        )
