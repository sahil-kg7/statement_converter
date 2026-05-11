from __future__ import annotations


def normalize_description(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise ValueError("Description is empty")
    return " ".join(value.split())
