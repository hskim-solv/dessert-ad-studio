from pathlib import Path

from PIL import Image

from dessert_ad_studio.banner_overlay import (
    BannerCopy,
    build_demo_product_analysis,
    create_banner_overlay,
)
from dessert_ad_studio.schemas import GenerationRequest


def _request(reference_image_name: str | None = "cake.jpg") -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="딸기 생크림 케이크",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="주말 10% 할인",
        user_constraints="20대 여성 타깃, 감성적인 인스타그램 홍보",
        reference_image_name=reference_image_name,
    )


def _count_changed_pixels_in_lower_overlay(
    image: Image.Image,
    source_color: tuple[int, int, int],
    *,
    start_ratio: float = 0.58,
    channel_tolerance: int = 10,
) -> int:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    start_y = int(height * start_ratio)
    expected = (*source_color, 255)
    changed_pixels = 0

    for y in range(start_y, height):
        for x in range(width):
            pixel = rgba.getpixel((x, y))
            if any(
                abs(pixel[channel] - expected[channel]) > channel_tolerance for channel in range(4)
            ):
                changed_pixels += 1

    return changed_pixels


def test_create_banner_overlay_writes_png(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source_color = (240, 220, 210)
    Image.new("RGB", (900, 900), color=source_color).save(source)
    copy = BannerCopy(
        headline="딸기 케이크 주말 할인",
        body="상큼한 딸기와 부드러운 생크림을 오늘 만나보세요.",
        call_to_action="지금 예약하기",
    )

    output = create_banner_overlay(
        image_path=source,
        copy=copy,
        price_text="주말 10% 할인",
        output_dir=tmp_path / "banners",
    )

    assert output.exists()
    assert output.suffix == ".png"
    assert output.parent == tmp_path / "banners"
    assert output.name == "source_banner.png"
    with Image.open(output) as image:
        assert image.size == (900, 900)
        assert image.mode == "RGBA"
        assert _count_changed_pixels_in_lower_overlay(image, source_color) > 900 * 900 * 0.05


def test_create_banner_overlay_handles_long_korean_text(tmp_path: Path) -> None:
    source = tmp_path / "long.png"
    source_color = (245, 240, 232)
    Image.new("RGB", (720, 720), color=source_color).save(source)
    copy = BannerCopy(
        headline="매장에서 직접 만든 진한 딸기 생크림 케이크를 이번 주말 한정 특별한 가격으로 만나보세요",
        body="신선한 딸기와 부드러운 크림을 듬뿍 올린 선물용 디저트입니다. 예약 주문도 가능합니다.",
        call_to_action="프로필 링크에서 예약",
    )

    output = create_banner_overlay(
        image_path=source,
        copy=copy,
        price_text="2호 케이크 예약 시 아메리카노 증정",
        output_dir=tmp_path / "banners",
        font_paths=[tmp_path / "missing-font.ttf"],
    )

    assert output.exists()
    with Image.open(output) as image:
        assert image.size == (720, 720)
        assert _count_changed_pixels_in_lower_overlay(image, source_color) > 720 * 720 * 0.05


def test_create_banner_overlay_handles_small_image(tmp_path: Path) -> None:
    source = tmp_path / "small.png"
    Image.new("RGB", (48, 48), color=(240, 220, 210)).save(source)
    copy = BannerCopy(
        headline="케이크",
        body="오늘 할인",
        call_to_action="예약",
    )

    output = create_banner_overlay(
        image_path=source,
        copy=copy,
        price_text="10%",
        output_dir=tmp_path / "banners",
    )

    assert output.exists()
    with Image.open(output) as image:
        assert image.size == (48, 48)


def test_build_demo_product_analysis_with_reference_image() -> None:
    analysis = build_demo_product_analysis(_request(reference_image_name="cake.jpg"))

    assert analysis["label"] == "Product analysis"
    assert analysis["analyzer_backend"] == "mock"
    assert analysis["product_context"] == "딸기 생크림 케이크 / 디저트 카페 상품"
    assert "할인/프로모션" in analysis["ad_goal"]
    assert "따뜻한" in analysis["visual_strategy"]
    assert "업로드된 제품 사진" in analysis["photo_strategy"]
    assert "오버레이" in analysis["rendering_strategy"]


def test_build_demo_product_analysis_without_reference_image() -> None:
    analysis = build_demo_product_analysis(_request(reference_image_name=None))

    assert "참고 이미지 없음" in analysis["photo_strategy"]
