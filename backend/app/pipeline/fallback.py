from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.normalize.amount import clean_amount_text
from app.normalize.date import normalize_transaction_date
from app.normalize.description import normalize_description
from app.pipeline.errors import UnsupportedStatementError
from app.pipeline.models import Transaction

DATE_PREFIX_PATTERN = re.compile(
    r"^(?P<date>\d{2}[-/]\d{2}[-/]\d{4}|\d{2}-[A-Za-z]{3}-\d{4}|\d{2}\s+[A-Za-z]{3}\s+\d{4})\b"
)
AMOUNT_PATTERN = re.compile(
    r"(?P<token>[+-]?\s*(?:₹|INR|Rs\.?|C)?\s*\(?\d[\d,]*\.\d{2}\)?(?:\s*(?:CR|DR|Cr|Dr|C))?)"
)
POSITIVE_HINTS = (
    " credit ",
    " deposit ",
    " refund ",
    " reversed ",
    "cr",
    "received",
    " from ",
)
NEGATIVE_HINTS = (
    " debit ",
    " withdrawal ",
    " purchase ",
    " fee ",
    " charge ",
    " dr",
    "spent",
)
NAME_PATTERN = re.compile(r"^[A-Z][A-Z\s\.]{2,}$")
PAGE_BREAK_PATTERN = re.compile(r"\f")


class LlmTransaction(BaseModel):
    date: str
    description: str
    amount: Decimal


class LlmStatement(BaseModel):
    bank_guess: str | None = None
    statement_kind: str | None = None
    transactions: list[LlmTransaction]


@dataclass(frozen=True)
class FallbackResult:
    transactions: list[Transaction]
    layers_tried: list[str]
    detected_bank: str | None
    detected_kind: str | None


def run_fallback_chain(
    payload: bytes,
    extracted_text: str,
    *,
    detected_bank: str | None = None,
    detected_kind: str | None = None,
    layers_tried: list[str] | None = None,
) -> FallbackResult:
    attempted_layers = list(layers_tried or [])
    generic_layer = "generic_pdf"
    attempted_layers.append(generic_layer)

    generic_transactions = _parse_generic_pdf_rows(extracted_text)
    if len(generic_transactions) >= max(1, settings.min_rows_threshold):
        return FallbackResult(
            transactions=generic_transactions,
            layers_tried=attempted_layers,
            detected_bank=detected_bank,
            detected_kind=detected_kind,
        )

    provider = settings.llm_provider.strip().lower()
    if provider == "none":
        raise UnsupportedStatementError(
            detected_bank=detected_bank,
            detected_kind=detected_kind,
            layers_tried=attempted_layers,
        )

    llm_layer = f"llm:{provider}"
    attempted_layers.append(llm_layer)
    llm_transactions = _parse_with_llm(provider, payload, extracted_text)
    if len(llm_transactions) >= 1:
        return FallbackResult(
            transactions=llm_transactions,
            layers_tried=attempted_layers,
            detected_bank=detected_bank,
            detected_kind=detected_kind,
        )

    raise UnsupportedStatementError(
        detected_bank=detected_bank,
        detected_kind=detected_kind,
        layers_tried=attempted_layers,
    )


def redact_statement_text(extracted_text: str) -> str:
    redacted = re.sub(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b", "<PHONE>", extracted_text)
    redacted = re.sub(r"\b\d{9,18}\b", "<ACCT>", redacted)
    redacted = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "<CARD>", redacted)
    redacted = re.sub(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", "<IFSC>", redacted)
    redacted = re.sub(r"\b[A-Z]{5}\d{4}[A-Z]\b", "<PAN>", redacted)
    redacted = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "<EMAIL>", redacted)

    lines = redacted.splitlines()
    for index, line in enumerate(lines[:-1]):
        if "<ACCT>" in lines[index + 1] and NAME_PATTERN.fullmatch(line.strip()):
            lines[index] = "<NAME>"
            break
    return "\n".join(lines)


def _parse_generic_pdf_rows(extracted_text: str) -> list[Transaction]:
    candidate_rows = _coalesce_statement_rows(extracted_text)
    transactions: list[Transaction] = []
    consecutive_successes = 0

    for row in candidate_rows:
        try:
            transactions.append(_parse_candidate_row(row))
            consecutive_successes += 1
        except ValueError:
            consecutive_successes = 0
            continue

    if consecutive_successes >= 3 or len(transactions) >= 3:
        return transactions
    return []


def _coalesce_statement_rows(extracted_text: str) -> list[str]:
    rows: list[str] = []
    current: str | None = None
    for raw_line in PAGE_BREAK_PATTERN.sub("\n", extracted_text).splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if DATE_PREFIX_PATTERN.match(line):
            if current is not None:
                rows.append(current)
            current = line
            continue
        if current is not None and not _looks_like_non_transaction_header(line):
            current = f"{current} {line}"
    if current is not None:
        rows.append(current)
    return rows


def _looks_like_non_transaction_header(line: str) -> bool:
    lower_line = f" {line.lower()} "
    header_tokens = (
        " statement ",
        " page ",
        " opening balance ",
        " closing balance ",
        " summary ",
    )
    return any(token in lower_line for token in header_tokens)


def _parse_candidate_row(row: str) -> Transaction:
    date_match = DATE_PREFIX_PATTERN.match(row)
    if date_match is None:
        raise ValueError("Row does not start with a transaction date")

    transaction_date = normalize_transaction_date(date_match.group("date"))
    remainder = row[date_match.end() :].strip()
    amount_matches = list(AMOUNT_PATTERN.finditer(remainder))
    if not amount_matches:
        raise ValueError("No amount found in row")

    transaction_match = (
        amount_matches[-2] if len(amount_matches) >= 2 else amount_matches[-1]
    )
    description = normalize_description(remainder[: transaction_match.start()].strip())
    amount = _coerce_signed_amount(transaction_match.group("token"), remainder)
    return Transaction(
        transaction_date=transaction_date, description=description, amount=amount
    )


def _coerce_signed_amount(token: str, row_text: str) -> Decimal:
    normalized = clean_amount_text(token)
    suffix = token.strip().upper()
    lower_row = f" {row_text.lower()} "

    if normalized.startswith("-") or (
        normalized.startswith("(") and normalized.endswith(")")
    ):
        return -Decimal(normalized.strip("()"))
    if normalized.startswith("+"):
        return Decimal(normalized[1:])
    if suffix.endswith("CR") or suffix.endswith(" C"):
        return Decimal(
            clean_amount_text(
                token.replace("CR", "").replace("Cr", "").replace(" C", "")
            )
        )
    if suffix.endswith("DR"):
        return -Decimal(clean_amount_text(token.replace("DR", "").replace("Dr", "")))
    if any(hint in lower_row for hint in POSITIVE_HINTS) and not any(
        hint in lower_row for hint in NEGATIVE_HINTS
    ):
        return Decimal(normalized)
    if any(hint in lower_row for hint in NEGATIVE_HINTS):
        return -Decimal(normalized)
    return -Decimal(normalized)


def _parse_with_llm(
    provider: str, payload: bytes, extracted_text: str
) -> list[Transaction]:
    del payload
    prompt_text = redact_statement_text(extracted_text)
    if provider == "groq":
        return _parse_with_groq(prompt_text)
    if provider == "ollama":
        if settings.llm_redact_local:
            return _parse_with_ollama(prompt_text)
        return _parse_with_ollama(extracted_text)
    raise UnsupportedStatementError(
        detected_bank=None,
        detected_kind=None,
        layers_tried=[f"llm:{provider}"],
        detail=f"Unsupported LLM provider: {provider}",
    )


def _parse_with_groq(prompt_text: str) -> list[Transaction]:
    if not settings.groq_api_key:
        return []

    payload = {
        "model": settings.groq_model,
        "temperature": 0,
        "messages": _build_llm_messages(prompt_text),
    }
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError):
        return []

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    return _transactions_from_llm_content(content)


def _parse_with_ollama(prompt_text: str) -> list[Transaction]:
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": _build_llm_messages(prompt_text),
    }
    request = Request(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError):
        return []

    content = body.get("message", {}).get("content", "")
    return _transactions_from_llm_content(content)


def _build_llm_messages(prompt_text: str) -> list[dict[str, str]]:
    bounded_prompt = prompt_text[: settings.max_llm_chars]
    return [
        {
            "role": "system",
            "content": (
                "You are a deterministic bank-statement parser. Output only JSON matching "
                "the schema {bank_guess, statement_kind, transactions:[{date,description,amount}]}. "
                "Never invent rows. Skip totals, summaries, and balances."
            ),
        },
        {
            "role": "user",
            "content": bounded_prompt,
        },
    ]


def _transactions_from_llm_content(content: str) -> list[Transaction]:
    raw_json = _extract_json_object(content)
    if raw_json is None:
        return []

    try:
        parsed = LlmStatement.model_validate(json.loads(raw_json))
    except (json.JSONDecodeError, ValidationError):
        return []

    transactions: list[Transaction] = []
    for item in parsed.transactions:
        try:
            transactions.append(
                Transaction(
                    transaction_date=normalize_transaction_date(item.date),
                    description=normalize_description(item.description),
                    amount=item.amount,
                )
            )
        except ValueError:
            continue
    return transactions


def _extract_json_object(content: str) -> str | None:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return content[start : end + 1]
