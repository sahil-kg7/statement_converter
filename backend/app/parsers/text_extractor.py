from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass(frozen=True)
class ExtractedPdfText:
    text: str
    page_count: int | None


def _find_executable(*candidates: str) -> str | None:
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _extract_page_count(pdf_path: Path) -> int | None:
    pdfinfo_executable = _find_executable("pdfinfo.exe", "pdfinfo")
    if pdfinfo_executable is None:
        return None

    completed = subprocess.run(
        [pdfinfo_executable, str(pdf_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None

    match = re.search(r"^Pages:\s+(\d+)$", completed.stdout, flags=re.MULTILINE)
    if match is None:
        return None
    return int(match.group(1))


def extract_pdf_text(payload: bytes) -> ExtractedPdfText:
    pdftotext_executable = _find_executable("pdftotext.exe", "pdftotext")
    if pdftotext_executable is None:
        raise ValueError("PDF conversion requires pdftotext to be installed")

    with tempfile.TemporaryDirectory(prefix="statement-converter-") as temp_dir:
        temp_path = Path(temp_dir)
        pdf_path = temp_path / "statement.pdf"
        text_path = temp_path / "statement.txt"
        pdf_path.write_bytes(payload)

        page_count = _extract_page_count(pdf_path)
        if page_count is not None and page_count > settings.max_pdf_pages:
            raise ValueError("PDF exceeds the configured page limit")

        completed = subprocess.run(
            [pdftotext_executable, "-layout", str(pdf_path), str(text_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or "pdftotext failed"
            raise ValueError(f"Could not extract text from PDF: {stderr}")

        text = text_path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            raise ValueError("Image-based PDFs are not supported")

    return ExtractedPdfText(text=text, page_count=page_count)
