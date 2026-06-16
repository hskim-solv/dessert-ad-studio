from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from dessert_ad_studio.schemas import GenerationRequest, MarketingContext, ProductAnalysis


@runtime_checkable
class MarketingContextRetriever(Protocol):
    name: str

    def retrieve(
        self,
        request: GenerationRequest,
        product_analysis: ProductAnalysis,
    ) -> MarketingContext: ...


@dataclass(frozen=True)
class _GuideDoc:
    doc_id: str
    category: str
    keywords: tuple[str, ...]
    copy_guidelines: tuple[str, ...] = ()
    tone_examples: tuple[str, ...] = ()
    platform_notes: tuple[str, ...] = ()
    prohibited_claims: tuple[str, ...] = ()
    cta_examples: tuple[str, ...] = ()


_GUIDE_DOCS = (
    _GuideDoc(
        doc_id="guide-cafe-dessert-core-v1",
        category="cafe",
        keywords=("카페", "디저트", "케이크", "푸딩", "마들렌", "크루아상", "cake", "dessert"),
        copy_guidelines=(
            "상품의 맛과 질감보다 방문 동기와 구매 순간을 먼저 제시한다.",
            "매장 방문, 예약, 포장 주문 중 하나의 행동을 분명히 유도한다.",
        ),
        tone_examples=(
            "따뜻한 톤은 여유, 휴식, 오늘의 작은 보상을 중심으로 쓴다.",
            "깔끔한 톤은 재료, 형태, 가격 정보를 짧게 정리한다.",
        ),
        cta_examples=("오늘 매장에서 만나보세요.", "SNS 저장 후 방문해보세요."),
    ),
    _GuideDoc(
        doc_id="guide-instagram-sns-v1",
        category="instagram",
        keywords=("인스타그램", "instagram", "sns", "게시물", "피드", "릴스", "해시태그"),
        copy_guidelines=(
            "첫 문장은 상품명이나 혜택이 바로 보이게 짧게 쓴다.",
            "본문은 저장, 공유, 방문 중 하나의 행동으로 마무리한다.",
        ),
        platform_notes=(
            "해시태그는 상품명, 지역, 메뉴 유형을 섞어 3~5개 수준으로 제한한다.",
            "인스타그램 피드 문구는 줄바꿈을 짧게 두어 모바일에서 읽기 쉽게 만든다.",
        ),
        cta_examples=("저장해두고 이번 주말 방문해보세요.",),
    ),
    _GuideDoc(
        doc_id="guide-discount-clarity-v1",
        category="discount",
        keywords=("discount", "할인", "혜택", "프로모션", "쿠폰", "10%"),
        copy_guidelines=(
            "할인율, 적용 기간, 적용 조건을 분리해서 모호하지 않게 쓴다.",
            "혜택을 강조하되 정상가 오해를 부르는 표현은 피한다.",
        ),
        cta_examples=("혜택이 끝나기 전에 확인하세요.",),
    ),
    _GuideDoc(
        doc_id="guide-premium-tone-v1",
        category="premium",
        keywords=("프리미엄", "premium", "고급", "선물", "minimal_premium"),
        copy_guidelines=("프리미엄 톤은 과한 감탄사보다 재료, 정성, 선물 맥락을 강조한다.",),
        tone_examples=("프리미엄 톤은 짧은 문장과 절제된 수식어를 우선한다.",),
    ),
    _GuideDoc(
        doc_id="guide-ad-claims-safety-v1",
        category="prohibited_claims",
        keywords=(),
        prohibited_claims=(
            "근거 없는 건강 효능, 치료 효과, 과장된 1위 표현을 쓰지 않는다.",
            "원산지, 수상 이력, 인증 문구는 요청에 명시된 근거가 없으면 추가하지 않는다.",
        ),
    ),
)


class NoopMarketingContextRetriever:
    name = "none"

    def retrieve(
        self,
        request: GenerationRequest,
        product_analysis: ProductAnalysis,
    ) -> MarketingContext:
        return MarketingContext(retriever_backend=self.name)


class KeywordMarketingContextRetriever:
    name = "keyword"

    def retrieve(
        self,
        request: GenerationRequest,
        product_analysis: ProductAnalysis,
    ) -> MarketingContext:
        haystack = _context_haystack(request, product_analysis)
        matched_docs = [
            doc
            for doc in _GUIDE_DOCS
            if doc.category == "prohibited_claims"
            or any(keyword.lower() in haystack for keyword in doc.keywords)
        ]
        return MarketingContext(
            retriever_backend=self.name,
            guide_categories=_unique(doc.category for doc in matched_docs),
            copy_guidelines=_unique(
                guideline for doc in matched_docs for guideline in doc.copy_guidelines
            ),
            tone_examples=_unique(example for doc in matched_docs for example in doc.tone_examples),
            platform_notes=_unique(note for doc in matched_docs for note in doc.platform_notes),
            prohibited_claims=_unique(
                claim for doc in matched_docs for claim in doc.prohibited_claims
            ),
            cta_examples=_unique(example for doc in matched_docs for example in doc.cta_examples),
            source_doc_ids=[doc.doc_id for doc in matched_docs],
            retrieved_docs_count=len(matched_docs),
        )


def _context_haystack(request: GenerationRequest, product_analysis: ProductAnalysis) -> str:
    values = [
        request.campaign_purpose,
        request.product_name,
        request.tone,
        request.template_hint,
        request.price_text,
        request.user_constraints,
        product_analysis.product_context,
        product_analysis.ad_goal,
        product_analysis.visual_strategy,
        product_analysis.copy_focus,
        product_analysis.detected_product_name,
        *product_analysis.mood_keywords,
        *product_analysis.selling_points,
    ]
    return " ".join(value.lower() for value in values if value)


def _unique(values) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
