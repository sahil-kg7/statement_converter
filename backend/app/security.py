from __future__ import annotations

from pathlib import Path

from app.config import settings


TEXT_SUFFIXES = {".csv", ".tsv", ".txt"}
UNSUPPORTED_SUFFIXES = {".xlsx", ".xls"}


def enforce_upload_limits(file_name: str, payload: bytes) -> None:
    if len(payload) > settings.max_upload_bytes:
        raise ValueError("File exceeds the configured upload limit")

    suffix = Path(file_name).suffix.lower()
    if suffix in UNSUPPORTED_SUFFIXES:
        raise ValueError("Excel uploads are not supported yet; convert to CSV first")


def is_pdf(payload: bytes) -> bool:
    return payload.startswith(b"%PDF-")


def is_text_upload(file_name: str, payload: bytes) -> bool:
    suffix = Path(file_name).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return True

    try:
        payload.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False
