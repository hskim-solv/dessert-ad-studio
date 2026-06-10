from __future__ import annotations

from pathlib import Path

from dessert_ad_studio.backends.naming import safe_filename_stem
from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.schemas import GenerationRequest


def sample_request(product_name: str) -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name=product_name,
        tone="playful",
        template_hint="cute_dessert",
    )


# ---------------------------------------------------------------------------
# Unit tests for safe_filename_stem
# ---------------------------------------------------------------------------


def test_korean_name_with_spaces_becomes_underscores() -> None:
    assert safe_filename_stem("벚꽃 딸기 케이크") == "벚꽃_딸기_케이크"


def test_relative_traversal_produces_separator_free_stem() -> None:
    result = safe_filename_stem("../../etc/passwd")
    assert "/" not in result
    assert "\\" not in result
    assert result == "passwd"


def test_absolute_path_produces_basename_only() -> None:
    result = safe_filename_stem("/etc/passwd")
    assert "/" not in result
    assert result == "passwd"


def test_backslash_input_produces_separator_free_stem() -> None:
    result = safe_filename_stem("foo\\bar")
    assert "/" not in result
    assert "\\" not in result
    assert result == "bar"


def test_empty_string_falls_back_to_product() -> None:
    assert safe_filename_stem("") == "product"


def test_normal_name_passes_through() -> None:
    assert safe_filename_stem("normal_name") == "normal_name"


# ---------------------------------------------------------------------------
# Integration test: traversal product_name stays inside output_dir
# ---------------------------------------------------------------------------


def test_mock_backend_traversal_stays_inside_output_dir(tmp_path: Path) -> None:
    backend = MockAdBackend(output_dir=tmp_path)
    result = backend.generate_image(
        sample_request("../../etc/passwd"), image_prompt="지시문"
    )
    assert Path(result).resolve().is_relative_to(tmp_path.resolve())


def test_openai_image_backend_traversal_stays_inside_output_dir(tmp_path: Path) -> None:
    import base64
    import io
    from types import SimpleNamespace
    from PIL import Image
    from dessert_ad_studio.backends.openai_image import OpenAIImageBackend

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, format="PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    client = SimpleNamespace(
        images=SimpleNamespace(
            generate=lambda **kw: SimpleNamespace(
                data=[SimpleNamespace(b64_json=b64)], usage=None
            )
        )
    )
    backend = OpenAIImageBackend(output_dir=tmp_path, client=client)
    result = backend.generate_image(
        sample_request("../../etc/passwd"), image_prompt="지시문"
    )
    assert Path(result).resolve().is_relative_to(tmp_path.resolve())
