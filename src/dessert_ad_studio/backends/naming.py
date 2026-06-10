from __future__ import annotations

from pathlib import PureWindowsPath


def safe_filename_stem(product_name: str) -> str:
    """Turn a user-supplied product name into a directory-safe filename stem."""
    stem = product_name.replace(" ", "_")
    stem = PureWindowsPath(stem).name  # strips both / and \ components and drive prefixes
    stem = "".join(ch for ch in stem if ch.isprintable())
    return stem or "product"
