from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CampaignPurpose = Literal["new_menu", "seasonal_event", "discount", "brand_awareness"]
Tone = Literal["warm", "premium", "playful", "clean"]
TemplateHint = Literal["cozy_cafe", "minimal_premium", "cute_dessert", "seasonal_event"]


class GenerationRequest(BaseModel):
    campaign_purpose: CampaignPurpose
    product_name: str = Field(min_length=1, max_length=80)
    tone: Tone
    template_hint: TemplateHint
    price_text: str = Field(default="", max_length=40)
    user_constraints: str = Field(default="", max_length=300)
    revision_request: str = Field(default="", max_length=200)
    reference_image_b64: str | None = None
    reference_image_name: str | None = None


class CopyOption(BaseModel):
    headline: str
    body: str
    call_to_action: str


class TemplateRanking(BaseModel):
    template_name: TemplateHint
    score: float
    scorer: str
    latency_ms: float


class ProductAnalysis(BaseModel):
    label: str
    product_context: str
    ad_goal: str
    visual_strategy: str
    photo_strategy: str
    copy_focus: str
    rendering_strategy: str
    analyzer_backend: str
    detected_product_name: str = ""
    dominant_colors: list[str] = Field(default_factory=list)
    mood_keywords: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    quality_notes: list[str] = Field(default_factory=list)
    recommended_background: str = ""
    preservation_notes: list[str] = Field(default_factory=list)


class MarketingContext(BaseModel):
    retriever_backend: str = "none"
    guide_categories: list[str] = Field(default_factory=list)
    copy_guidelines: list[str] = Field(default_factory=list)
    tone_examples: list[str] = Field(default_factory=list)
    platform_notes: list[str] = Field(default_factory=list)
    prohibited_claims: list[str] = Field(default_factory=list)
    cta_examples: list[str] = Field(default_factory=list)
    source_doc_ids: list[str] = Field(default_factory=list)
    retrieved_docs_count: int = 0


class GenerationResponse(BaseModel):
    copy_options: list[CopyOption]
    selected_template: TemplateRanking
    image_path: str
    image_backend: str
    copy_backend: str
    used_reference: bool
    prompt_summary: str
    elapsed_ms: float
    product_analysis: ProductAnalysis
    marketing_context: MarketingContext = Field(default_factory=MarketingContext)
