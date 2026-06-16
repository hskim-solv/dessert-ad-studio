from __future__ import annotations

from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont

from dessert_ad_studio.backends.base import CopyResult, ImageResult
from dessert_ad_studio.backends.naming import safe_filename_stem
from dessert_ad_studio.schemas import (
    CopyOption,
    GenerationRequest,
    MarketingContext,
    ProductAnalysis,
)


class MockAdBackend:
    name = "mock"
    supports_reference_image = True

    def __init__(self, output_dir: str | Path = "outputs") -> None:
        self.output_dir = Path(output_dir)

    def generate_copy(
        self,
        request: GenerationRequest,
        *,
        product_analysis: ProductAnalysis | None = None,
        marketing_context: MarketingContext | None = None,
    ) -> CopyResult:
        product = request.product_name
        options = [
            CopyOption(
                headline=f"{product}, 오늘의 달콤한 선택",
                body=f"{request.price_text or '지금 매장에서'} 만나는 기분 좋은 디저트 타임.",
                call_to_action="오늘 매장에서 만나보세요.",
            ),
            CopyOption(
                headline=f"{product}로 채우는 카페 한 컷",
                body="따뜻한 커피와 잘 어울리는 시즌 추천 메뉴입니다.",
                call_to_action="SNS 저장하고 방문해보세요.",
            ),
            CopyOption(
                headline=f"작지만 확실한 행복, {product}",
                body="부담 없이 즐기는 달콤함을 깔끔한 광고 톤으로 전합니다.",
                call_to_action="지금 바로 주문하세요.",
            ),
        ]
        return CopyResult(options=options)

    def generate_image(
        self,
        request: GenerationRequest,
        image_prompt: str,
        reference_image: bytes | None = None,
    ) -> ImageResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_ref" if reference_image is not None else ""
        filename = f"{safe_filename_stem(request.product_name)}_mock_ad{suffix}.png"
        path = self.output_dir / filename

        image = Image.new("RGB", (1024, 1024), color=(250, 238, 224))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.rounded_rectangle(
            (90, 120, 934, 780),
            radius=48,
            fill=(255, 250, 244),
            outline=(120, 80, 60),
            width=4,
        )
        draw.ellipse((332, 230, 692, 590), fill=(230, 120, 140), outline=(90, 60, 50), width=4)
        if reference_image is not None:
            draw.rectangle((40, 40, 200, 120), fill=(40, 160, 90))
            draw.text((70, 70), "REF", fill=(255, 255, 255), font=font)
        draw.text((140, 830), request.product_name, fill=(80, 45, 35), font=font)
        prompt_line = textwrap.shorten(image_prompt.replace("\n", " "), width=90)
        draw.text((140, 870), prompt_line, fill=(110, 80, 70), font=font)
        image.save(path)
        return ImageResult(path=str(path))
