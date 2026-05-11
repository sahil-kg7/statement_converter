from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.pipeline.models import Transaction


@dataclass(frozen=True)
class CsvParseContext:
    source_path: Path


class CsvBankParser(Protocol):
    def matches(self, raw_text: str) -> bool: ...

    def parse(self, raw_text: str, context: CsvParseContext) -> list[Transaction]: ...
