from __future__ import annotations

from dataclasses import dataclass

from dessert_ad_studio.schemas import GenerationRequest


@dataclass(frozen=True)
class MarketingContextEvalCase:
    label: str
    request: GenerationRequest
    expected_categories: tuple[str, ...]


MARKETING_CONTEXT_EVAL_CASES: tuple[MarketingContextEvalCase, ...] = (
    MarketingContextEvalCase(
        label="instagram-cafe-new-menu",
        request=GenerationRequest(
            campaign_purpose="new_menu",
            product_name="딸기 크림 크루아상",
            tone="warm",
            template_hint="cozy_cafe",
            price_text="6,800원",
            user_constraints="인스타그램 피드, 디저트 카페 신메뉴, 20대 여성 타깃",
        ),
        expected_categories=("cafe", "instagram", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="premium-seasonal-dessert",
        request=GenerationRequest(
            campaign_purpose="seasonal_event",
            product_name="말차 푸딩",
            tone="premium",
            template_hint="minimal_premium",
            price_text="2개 세트 9,900원",
            user_constraints="인스타그램 스토리, 진한 말차 풍미, 시즌 한정 선물용",
        ),
        expected_categories=("cafe", "instagram", "premium", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="discount-promotion",
        request=GenerationRequest(
            campaign_purpose="discount",
            product_name="봄 플라워 박스",
            tone="playful",
            template_hint="seasonal_event",
            price_text="예약 주문 10% 할인",
            user_constraints="네이버 스마트스토어 썸네일, 선물용 추천, 주말 예약 주문 유도",
        ),
        expected_categories=("discount", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="premium-cake-gift",
        request=GenerationRequest(
            campaign_purpose="brand_awareness",
            product_name="초코 가나슈 케이크",
            tone="premium",
            template_hint="minimal_premium",
            price_text="32,000원",
            user_constraints="프리미엄 선물용, 고급스러운 패키지 강조",
        ),
        expected_categories=("cafe", "premium", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="sns-reels-madeleine",
        request=GenerationRequest(
            campaign_purpose="new_menu",
            product_name="바닐라 마들렌",
            tone="playful",
            template_hint="cute_dessert",
            price_text="3개 세트 7,500원",
            user_constraints="릴스 짧은 게시물, SNS 저장 유도, 귀여운 디저트 톤",
        ),
        expected_categories=("cafe", "instagram", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="coupon-cheesecake",
        request=GenerationRequest(
            campaign_purpose="discount",
            product_name="레몬 치즈케이크",
            tone="clean",
            template_hint="cozy_cafe",
            price_text="쿠폰 사용 시 10% 할인",
            user_constraints="주말 프로모션, 포장 주문 유도",
        ),
        expected_categories=("cafe", "discount", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="signature-cafe-brand",
        request=GenerationRequest(
            campaign_purpose="brand_awareness",
            product_name="시그니처 크루아상",
            tone="warm",
            template_hint="cozy_cafe",
            price_text="5,800원",
            user_constraints="카페 대표 메뉴, 매장 방문 유도",
        ),
        expected_categories=("cafe", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="premium-flower-gift",
        request=GenerationRequest(
            campaign_purpose="brand_awareness",
            product_name="봄 플라워 박스",
            tone="premium",
            template_hint="minimal_premium",
            price_text="45,000원",
            user_constraints="고급 선물용, 기념일 예약 주문",
        ),
        expected_categories=("premium", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="instagram-hashtag-cake",
        request=GenerationRequest(
            campaign_purpose="new_menu",
            product_name="딸기 생크림 케이크",
            tone="clean",
            template_hint="cute_dessert",
            price_text="조각 7,200원",
            user_constraints="인스타그램 피드, 해시태그, 신메뉴 게시물",
        ),
        expected_categories=("cafe", "instagram", "prohibited_claims"),
    ),
    MarketingContextEvalCase(
        label="benefit-pudding-set",
        request=GenerationRequest(
            campaign_purpose="discount",
            product_name="커스터드 푸딩",
            tone="warm",
            template_hint="cozy_cafe",
            price_text="2개 구매 혜택",
            user_constraints="퇴근길 포장 주문, 오늘의 작은 보상",
        ),
        expected_categories=("cafe", "discount", "prohibited_claims"),
    ),
)
