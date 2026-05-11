from __future__ import annotations

from pydantic import BaseModel


class UnsupportedStatementPayload(BaseModel):
    error: str = "unsupported_statement"
    detail: str = "Could not identify the bank or extract transactions."
    hints: dict[str, object]


class UnsupportedStatementError(ValueError):
    def __init__(
        self,
        *,
        detected_bank: str | None,
        detected_kind: str | None,
        layers_tried: list[str],
        detail: str = "Could not identify the bank or extract transactions.",
    ) -> None:
        super().__init__(detail)
        self.detected_bank = detected_bank
        self.detected_kind = detected_kind
        self.layers_tried = layers_tried
        self.detail = detail

    def to_payload(self) -> UnsupportedStatementPayload:
        return UnsupportedStatementPayload(
            detail=self.detail,
            hints={
                "detected_bank": self.detected_bank,
                "detected_kind": self.detected_kind,
                "layers_tried": self.layers_tried,
            },
        )
