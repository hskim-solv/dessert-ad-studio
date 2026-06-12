from __future__ import annotations

from dataclasses import dataclass

from dessert_ad_studio.schemas import CampaignPurpose, TemplateHint, Tone


@dataclass(frozen=True)
class DemoSample:
    label: str
    business_type: str
    platform: str
    product_name: str
    campaign_purpose: CampaignPurpose
    tone: Tone
    template_hint: TemplateHint
    price_text: str
    user_constraints: str


DEMO_SAMPLES: tuple[DemoSample, ...] = (
    DemoSample(
        label="디저트 카페 - 딸기 크림 크루아상",
        business_type="디저트 카페",
        platform="인스타그램 피드",
        product_name="딸기 크림 크루아상",
        campaign_purpose="new_menu",
        tone="warm",
        template_hint="cozy_cafe",
        price_text="6,800원",
        user_constraints="봄 시즌 한정 느낌, 따뜻한 카페 조명, 20대 여성 타깃",
    ),
    DemoSample(
        label="베이커리 - 말차 푸딩",
        business_type="베이커리",
        platform="인스타그램 스토리",
        product_name="말차 푸딩",
        campaign_purpose="seasonal_event",
        tone="premium",
        template_hint="minimal_premium",
        price_text="2개 세트 9,900원",
        user_constraints="진한 말차 풍미, 차분한 프리미엄 분위기, 시즌 한정 디저트",
    ),
    DemoSample(
        label="꽃집 - 플라워 박스",
        business_type="꽃집",
        platform="네이버 스마트스토어 썸네일",
        product_name="봄 플라워 박스",
        campaign_purpose="discount",
        tone="playful",
        template_hint="seasonal_event",
        price_text="예약 주문 10% 할인",
        user_constraints="선물용 추천, 화사한 봄 컬러, 주말 예약 주문 유도",
    ),
)
