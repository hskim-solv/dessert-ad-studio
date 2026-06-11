from __future__ import annotations

import os
from typing import Any

from openai import (
    APIError,
    AuthenticationError,
    BadRequestError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
from pydantic import BaseModel

from dessert_ad_studio.backends.base import AdBackendError, CopyResult
from dessert_ad_studio.prompts import COPY_OPTION_COUNT, build_copy_prompt
from dessert_ad_studio.schemas import CopyOption, GenerationRequest

COPY_SYSTEM_PROMPT = (
    "너는 카페/디저트 소상공인을 돕는 한국어 광고 카피라이터다. "
    "과장 광고, 허위 수상 문구, 근거 없는 효능 주장은 금지한다. "
    "각 후보는 헤드라인, 본문 한두 문장, 행동 유도 문구로 구성하며 "
    f"정확히 {COPY_OPTION_COUNT}개를 만든다."
)


class CopyOptionsPayload(BaseModel):
    options: list[CopyOption]


class OpenAICopyBackend:
    name = "openai"

    def __init__(self, model_id: str | None = None, client: Any | None = None) -> None:
        self.model_id = model_id or os.getenv("COPY_MODEL_ID", "gpt-5.4-mini")
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            if not os.getenv("OPENAI_API_KEY", "").strip():
                # A whitespace-only key would pass client construction and
                # only fail on the first paid call; treat it as unset now.
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                )
            try:
                self._client = OpenAI(timeout=120.0)
            except OpenAIError as exc:
                raise AdBackendError(
                    "OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 확인해주세요."
                ) from exc
        return self._client

    def generate_copy(self, request: GenerationRequest) -> CopyResult:
        client = self._get_client()
        try:
            completion = client.chat.completions.parse(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": COPY_SYSTEM_PROMPT},
                    {"role": "user", "content": build_copy_prompt(request)},
                ],
                response_format=CopyOptionsPayload,
            )
        except AuthenticationError as exc:
            raise AdBackendError(
                "OpenAI API 키가 유효하지 않습니다. 키 값을 확인해주세요."
            ) from exc
        except RateLimitError as exc:
            raise AdBackendError(
                "OpenAI API 호출 한도를 초과했습니다. 잠시 후 다시 시도하거나 팀 사용량을 확인해주세요."
            ) from exc
        except BadRequestError as exc:
            raise AdBackendError(
                f"문구 생성 요청이 거부되었습니다: {exc}", status_code=422
            ) from exc
        except (ContentFilterFinishReasonError, LengthFinishReasonError) as exc:
            raise AdBackendError("광고 문구 생성이 중단되었습니다. 다시 시도해주세요.") from exc
        except APIError as exc:
            raise AdBackendError(f"문구 생성 API 호출에 실패했습니다: {exc}") from exc

        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise AdBackendError("광고 문구 응답을 해석하지 못했습니다. 다시 시도해주세요.")
        if len(parsed.options) != COPY_OPTION_COUNT:
            raise AdBackendError(
                f"광고 문구 {COPY_OPTION_COUNT}개 생성에 실패했습니다. 다시 시도해주세요."
            )
        usage = getattr(completion, "usage", None)
        usage_record = None
        if usage is not None:
            usage_record = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }
        return CopyResult(options=list(parsed.options), usage=usage_record)
