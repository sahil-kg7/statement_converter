from __future__ import annotations

from app.pipeline.models import Transaction


EXCLUDED_DESCRIPTION_TOKENS = (
    "opening balance",
    "closing balance",
    "current & saving account statement",
)


def should_skip_row(description: str, debit: str | None, credit: str | None) -> bool:
    normalized = description.strip().lower()
    if not normalized:
        return True
    if any(token in normalized for token in EXCLUDED_DESCRIPTION_TOKENS):
        return True
    if not (debit or credit):
        return True
    return False


def dedupe_transactions(transactions: list[Transaction]) -> list[Transaction]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[Transaction] = []
    for transaction in transactions:
        key = (
            transaction.transaction_date,
            transaction.description,
            format(transaction.amount, "f"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(transaction)
    return deduped
