from __future__ import annotations

from pydantic import BaseModel

from app.pipeline.models import Transaction


class HealthResponse(BaseModel):
    status: str


class ConversionPreviewResponse(BaseModel):
    detected_bank: str | None = None
    statement_kind: str | None = None
    conversion_source: str
    total_rows: int
    preview_rows: list[Transaction]
    download_token: str
    download_url: str
