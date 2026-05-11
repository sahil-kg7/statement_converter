from __future__ import annotations

from enum import StrEnum

from app.security import enforce_upload_limits, is_pdf, is_text_upload


class InputKind(StrEnum):
    PDF = "pdf"
    CSV = "csv"


def sniff_input_kind(file_name: str, payload: bytes) -> InputKind:
    enforce_upload_limits(file_name, payload)

    if is_pdf(payload):
        return InputKind.PDF
    if is_text_upload(file_name, payload):
        return InputKind.CSV
    raise ValueError("Unsupported file type")
