from __future__ import annotations

import csv
from io import StringIO

from app.normalize.amount import format_signed_amount
from app.pipeline.models import Transaction


OUTPUT_HEADERS = ["Transaction Date", "Description", "Amount (Debit/Credit)"]


def build_output_csv(transactions: list[Transaction]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(OUTPUT_HEADERS)
    for transaction in transactions:
        writer.writerow(
            [
                transaction.transaction_date,
                transaction.description,
                format_signed_amount(transaction.amount),
            ]
        )
    return buffer.getvalue()
