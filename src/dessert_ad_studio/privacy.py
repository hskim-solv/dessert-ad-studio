from __future__ import annotations

import hashlib
from typing import Any


def sha256_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def redacted_named_value(name: str, value: str | None) -> dict[str, Any]:
    return {
        f"has_{name}": bool(value),
        f"{name}_sha256": sha256_text(value),
    }


def redacted_image_path(value: str | None) -> dict[str, Any]:
    return redacted_named_value("image_path", value)


def redacted_log_path(value: str | None) -> dict[str, Any]:
    return redacted_named_value("log_path", value)


def redacted_reference_image_name(value: str | None) -> dict[str, Any]:
    return redacted_named_value("reference_image_name", value)
