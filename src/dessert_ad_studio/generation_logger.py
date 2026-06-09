from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class GenerationLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        enriched = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(enriched, ensure_ascii=False, sort_keys=True) + "\n")
