from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

from dessert_ad_studio.schemas import GenerationRequest


@dataclass(frozen=True)
class BannerCopy:
    headline: str
    body: str
    call_to_action: str


DEFAULT_FONT_PATHS = (
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
    Path("/Library/Fonts/AppleGothic.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
)

PURPOSE_LABELS = {
    "new_menu": "신메뉴 출시",
    "seasonal_event": "시즌 이벤트",
    "discount": "할인/프로모션",
    "brand_awareness": "브랜드 인지도",
}

TONE_LABELS = {
    "warm": "따뜻한",
    "premium": "프리미엄",
    "playful": "발랄한",
    "clean": "깔끔한",
}

TEMPLATE_LABELS = {
    "cozy_cafe": "코지 카페",
    "minimal_premium": "미니멀 프리미엄",
    "cute_dessert": "귀여운 디저트",
    "seasonal_event": "시즌 이벤트",
}

_ELLIPSIS = "..."


def create_banner_overlay(
    image_path: str | Path,
    copy: BannerCopy,
    price_text: str,
    output_dir: str | Path = "outputs/streamlit-banners",
    font_paths: Sequence[str | Path] | None = None,
) -> Path:
    source_path = Path(image_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / f"{source_path.stem}_banner.png"

    with Image.open(source_path) as source:
        image = source.convert("RGBA")

    width, height = image.size
    min_dimension = max(1, min(width, height))
    preferred_margin = max(28, min_dimension // 24)
    small_image_margin = max(1, min_dimension // 8)
    max_margin = max(0, (min_dimension - 1) // 2)
    margin = min(preferred_margin, small_image_margin, max_margin)
    panel_height = min(height - (margin * 2), max(height // 3, 260))
    panel_left = margin
    panel_top = height - panel_height - margin
    panel_right = width - margin
    panel_bottom = height - margin
    panel_width = max(1, panel_right - panel_left)
    panel_height = max(1, panel_bottom - panel_top)
    panel_radius = min(max(18, width // 45), panel_width // 2, panel_height // 2)

    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    overlay_draw.rounded_rectangle(
        (panel_left, panel_top, panel_right, panel_bottom),
        radius=panel_radius,
        fill=(18, 18, 18, 178),
    )
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image, "RGBA")

    headline_font = _load_font(max(30, width // 18), font_paths)
    body_font = _load_font(max(20, width // 34), font_paths)
    meta_font = _load_font(max(18, width // 38), font_paths)
    cta_font = _load_font(max(20, width // 32), font_paths)

    inset = min(max(22, width // 36), max(1, panel_width // 4))
    text_left = panel_left + inset
    text_right = panel_right - inset
    max_text_width = max(1, text_right - text_left)
    y = panel_top + max(22, height // 36)

    clean_price = price_text.strip()
    if clean_price:
        badge = _truncate_to_width(draw, clean_price, meta_font, max_text_width - 28)
        badge_box = _text_bbox(draw, badge, meta_font)
        badge_width = badge_box[2] - badge_box[0] + 28
        badge_height = badge_box[3] - badge_box[1] + 16
        draw.rounded_rectangle(
            (text_left, y, text_left + badge_width, y + badge_height),
            radius=badge_height // 2,
            fill=(255, 235, 180, 235),
        )
        _draw_text(draw, (text_left + 14, y + 7), badge, meta_font, (30, 24, 18, 255))
        y += badge_height + 14

    for line in _wrap_text(draw, copy.headline, headline_font, max_text_width, max_lines=2):
        _draw_text(draw, (text_left, y), line, headline_font, (255, 255, 255, 255))
        y += _line_height(draw, line, headline_font) + 6

    y += 4
    remaining_height = panel_bottom - y
    body_lines = 2 if remaining_height > 90 else 1
    for line in _wrap_text(draw, copy.body, body_font, max_text_width, max_lines=body_lines):
        _draw_text(draw, (text_left, y), line, body_font, (242, 242, 242, 245))
        y += _line_height(draw, line, body_font) + 5

    cta = _truncate_to_width(
        draw,
        copy.call_to_action.strip() or "방문하기",
        cta_font,
        max_text_width - 34,
    )
    cta_box = _text_bbox(draw, cta, cta_font)
    cta_width = cta_box[2] - cta_box[0] + 34
    cta_height = cta_box[3] - cta_box[1] + 20
    cta_x = text_left
    cta_y = min(panel_bottom - cta_height - 18, y + 16)
    draw.rounded_rectangle(
        (cta_x, cta_y, cta_x + cta_width, cta_y + cta_height),
        radius=cta_height // 2,
        fill=(255, 255, 255, 242),
    )
    _draw_text(draw, (cta_x + 17, cta_y + 9), cta, cta_font, (25, 25, 25, 255))

    image.save(destination)
    return destination


def build_demo_product_analysis(request: GenerationRequest) -> dict[str, str]:
    purpose = PURPOSE_LABELS[request.campaign_purpose]
    tone = TONE_LABELS[request.tone]
    template = TEMPLATE_LABELS[request.template_hint]
    promotion = request.price_text.strip() or "별도 가격/혜택 없음"
    constraints = request.user_constraints.strip() or "추가 요청 없음"
    photo_strategy = (
        "업로드된 제품 사진을 기준으로 상품 형태와 색감을 유지한 배너 구성을 제안합니다."
        if request.reference_image_name
        else "참고 이미지 없음: 상품명과 요청사항을 기준으로 디저트 광고 장면을 구성합니다."
    )

    return {
        "label": "Demo product analysis",
        "product_context": f"{request.product_name} / 디저트 카페 상품",
        "ad_goal": f"{purpose} 목적의 광고입니다. 혜택/가격: {promotion}",
        "visual_strategy": f"{tone} 톤과 {template} 템플릿에 맞춰 카페 광고 무드를 정리합니다.",
        "photo_strategy": photo_strategy,
        "copy_focus": f"카피는 상품 매력, 방문 동기, 요청사항({constraints})을 중심으로 구성합니다.",
        "rendering_strategy": "한글 문구, 가격 배지, CTA는 이미지 위에 PIL 오버레이로 렌더링합니다.",
    }


def _load_font(
    size: int,
    font_paths: Sequence[str | Path] | None = None,
) -> ImageFont.ImageFont:
    for path in _font_candidates(font_paths):
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _font_candidates(font_paths: Sequence[str | Path] | None) -> list[Path]:
    candidates: list[Path] = []
    seen: set[Path] = set()
    for raw_path in [*(font_paths or ()), *DEFAULT_FONT_PATHS]:
        path = Path(raw_path)
        if path in seen or not path.exists():
            continue
        seen.add(path)
        candidates.append(path)
    return candidates


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    normalized = " ".join(text.strip().split())
    if not normalized or max_width <= 0 or max_lines <= 0:
        return []

    remaining = normalized
    lines: list[str] = []
    while remaining and len(lines) < max_lines:
        line, remaining = _take_line(draw, remaining, font, max_width)
        if not line:
            break
        lines.append(line)

    if remaining and lines:
        lines[-1] = _truncate_to_width(draw, f"{lines[-1]}{_ELLIPSIS}", font, max_width)

    return lines


def _take_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> tuple[str, str]:
    current = ""
    last_break = -1
    for index, character in enumerate(text):
        candidate = f"{current}{character}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            if character.isspace():
                last_break = index
            continue

        if current and last_break >= 0:
            return text[:last_break].strip(), text[last_break + 1 :].lstrip()
        if current:
            return current.strip(), text[index:].lstrip()

        return _truncate_to_width(draw, character, font, max_width), text[index + 1 :].lstrip()

    return current.strip(), ""


def _truncate_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> str:
    value = text.strip()
    if not value or max_width <= 0:
        return ""
    if _text_width(draw, value, font) <= max_width:
        return value

    value = value.removesuffix(_ELLIPSIS).rstrip()
    if _text_width(draw, _ELLIPSIS, font) > max_width:
        return ""

    while value and _text_width(draw, f"{value}{_ELLIPSIS}", font) > max_width:
        value = value[:-1].rstrip()

    return f"{value}{_ELLIPSIS}" if value else _ELLIPSIS


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = _text_bbox(draw, text, font)
    return box[2] - box[0]


def _line_height(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = _text_bbox(draw, text or "Ag", font)
    return box[3] - box[1]


def _text_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> tuple[int, int, int, int]:
    try:
        return draw.textbbox((0, 0), text, font=font)
    except UnicodeEncodeError:
        return draw.textbbox((0, 0), _ascii_fallback_text(text), font=font)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int, int],
) -> None:
    try:
        draw.text(xy, text, fill=fill, font=font)
    except UnicodeEncodeError:
        draw.text(xy, _ascii_fallback_text(text), fill=fill, font=font)


def _ascii_fallback_text(text: str) -> str:
    return "".join(character if ord(character) < 128 else "?" for character in text)
