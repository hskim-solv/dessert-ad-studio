from types import SimpleNamespace

import pytest

from dessert_ad_studio.backends.base import AdBackendError
from dessert_ad_studio.backends.openai_copy import CopyOptionsPayload, OpenAICopyBackend
from dessert_ad_studio.schemas import CopyOption, GenerationRequest


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        campaign_purpose="discount",
        product_name="초코 마들렌",
        tone="playful",
        template_hint="cute_dessert",
        price_text="2개 구매 시 10% 할인",
    )


def make_payload(count: int = 3) -> CopyOptionsPayload:
    return CopyOptionsPayload(
        options=[
            CopyOption(
                headline=f"헤드라인 {index}",
                body=f"본문 {index}",
                call_to_action=f"행동 유도 {index}",
            )
            for index in range(count)
        ]
    )


class FakeCompletions:
    def __init__(self, payload: CopyOptionsPayload | None) -> None:
        self._payload = payload
        self.last_kwargs: dict | None = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=self._payload))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=88, total_tokens=208),
        )


def make_fake_client(payload: CopyOptionsPayload | None) -> SimpleNamespace:
    completions = FakeCompletions(payload)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_generate_copy_returns_three_options_and_records_usage() -> None:
    client = make_fake_client(make_payload())
    backend = OpenAICopyBackend(model_id="gpt-test-mini", client=client)

    options = backend.generate_copy(sample_request())

    assert [option.headline for option in options] == ["헤드라인 0", "헤드라인 1", "헤드라인 2"]
    assert backend.last_usage == {
        "prompt_tokens": 120,
        "completion_tokens": 88,
        "total_tokens": 208,
    }
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-test-mini"
    assert kwargs["response_format"] is CopyOptionsPayload
    assert kwargs["messages"][0]["role"] == "system"
    assert "초코 마들렌" in kwargs["messages"][1]["content"]


def test_generate_copy_rejects_wrong_option_count() -> None:
    backend = OpenAICopyBackend(client=make_fake_client(make_payload(count=2)))

    with pytest.raises(AdBackendError, match="3개"):
        backend.generate_copy(sample_request())


def test_missing_api_key_maps_to_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAICopyBackend()

    with pytest.raises(AdBackendError, match="OPENAI_API_KEY"):
        backend.generate_copy(sample_request())
