from pathlib import Path

from dessert_ad_studio.backends.mock import MockAdBackend
from dessert_ad_studio.prompts import build_image_prompt
from dessert_ad_studio.schemas import GenerationRequest


def test_mock_backend_returns_three_copy_options_and_image(tmp_path: Path) -> None:
    request = GenerationRequest(
        campaign_purpose="discount",
        product_name="초코 마들렌",
        tone="playful",
        template_hint="cute_dessert",
        price_text="2개 구매 시 10% 할인",
    )
    backend = MockAdBackend(output_dir=tmp_path)

    copy_options = backend.generate_copy(request)
    image_path = backend.generate_image(
        request=request,
        image_prompt=build_image_prompt(request, ranked_template="cute_dessert"),
    )

    assert len(copy_options) == 3
    assert copy_options[0].headline.startswith("초코 마들렌")
    assert Path(image_path).exists()
    assert Path(image_path).suffix == ".png"


REF_BADGE_COLOR = (40, 160, 90)


def test_mock_image_marks_reference_usage_with_badge(tmp_path: Path) -> None:
    request = GenerationRequest(
        campaign_purpose="new_menu",
        product_name="레몬 타르트",
        tone="clean",
        template_hint="minimal_premium",
    )
    backend = MockAdBackend(output_dir=tmp_path)
    prompt = build_image_prompt(request, ranked_template="minimal_premium")

    plain_path = backend.generate_image(request=request, image_prompt=prompt)
    badge_path = backend.generate_image(
        request=request, image_prompt=prompt, reference_image=b"fake-reference-bytes"
    )

    from PIL import Image

    with Image.open(plain_path) as plain:
        assert plain.getpixel((60, 60)) != REF_BADGE_COLOR
    with Image.open(badge_path) as badged:
        assert badged.getpixel((60, 60)) == REF_BADGE_COLOR
