from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4


@dataclass(frozen=True)
class CachedDownload:
    csv_text: str
    download_name: str
    expires_at: float


class DownloadCache:
    def __init__(self, ttl_seconds: int = 15 * 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, CachedDownload] = {}
        self._lock = Lock()

    def store(self, csv_text: str, *, source_name: str) -> str:
        token = uuid4().hex
        download_name = (
            f"{Path(source_name).stem or 'normalized-statement'}-normalized.csv"
        )
        entry = CachedDownload(
            csv_text=csv_text,
            download_name=download_name,
            expires_at=monotonic() + self.ttl_seconds,
        )
        with self._lock:
            self._purge_expired_locked()
            self._entries[token] = entry
        return token

    def get(self, token: str) -> CachedDownload | None:
        with self._lock:
            self._purge_expired_locked()
            return self._entries.get(token)

    def _purge_expired_locked(self) -> None:
        now = monotonic()
        expired = [
            token for token, entry in self._entries.items() if entry.expires_at <= now
        ]
        for token in expired:
            self._entries.pop(token, None)
