from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def hermetic_backend_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPY_BACKEND", "mock")
    monkeypatch.setenv("IMAGE_BACKEND", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
