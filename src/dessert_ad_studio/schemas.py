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
