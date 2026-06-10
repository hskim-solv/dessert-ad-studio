from types import SimpleNamespace

import httpx
import openai
import pytest

from dessert_ad_studio.backends.base import AdBackendError, CopyResult
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


def _make_httpx_response(status_code: int = 400) -> httpx.Response:
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return httpx.Response(status_code, request=req)


def _make_chat_completion() -> openai.types.chat.ChatCompletion:
    from openai.types.chat import ChatCompletion
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_message import ChatCompletionMessage

    return ChatCompletion(
        id="test-id",
        choices=[
            Choice(
                finish_reason="length",
                index=0,
                message=ChatCompletionMessage(role="assistant", content="hi"),
                logprobs=None,
            )
        ],
        created=1,
        model="gpt-4o-mini",
        object="chat.completion",
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


class RaisingCompletions:
    """FakeCompletions variant that raises a given SDK exception from parse()."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def parse(self, **kwargs):
        raise self._exc


def make_fake_client(payload: CopyOptionsPayload | None) -> SimpleNamespace:
    completions = FakeCompletions(payload)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


def test_generate_copy_returns_three_options_with_usage() -> None:
    client = make_fake_client(make_payload())
    backend = OpenAICopyBackend(model_id="gpt-test-mini", client=client)

    result = backend.generate_copy(sample_request())

    assert isinstance(result, CopyResult)
    assert [option.headline for option in result.options] == ["헤드라인 0", "헤드라인 1", "헤드라인 2"]
    assert result.usage == {
        "prompt_tokens": 120,
        "completion_tokens": 88,
        "total_tokens": 208,
    }
    kwargs = client.chat.completions.last_kwargs
    assert kwargs["model"] == "gpt-test-mini"
    assert kwargs["response_format"] is CopyOptionsPayload
    assert kwargs["messages"][0]["role"] == "system"
    assert "초코 마들렌" in kwargs["messages"][1]["content"]


def test_generate_copy_keeps_no_request_state_on_the_instance() -> None:
    """The API caches one backend per config and serves concurrent requests
    from a threadpool; per-request data must travel in the return value."""
    backend = OpenAICopyBackend(model_id="gpt-test-mini", client=make_fake_client(make_payload()))

    backend.generate_copy(sample_request())

    assert not hasattr(backend, "last_usage")


def test_generate_copy_rejects_wrong_option_count() -> None:
    backend = OpenAICopyBackend(client=make_fake_client(make_payload(count=2)))

    with pytest.raises(AdBackendError, match="3개"):
        backend.generate_copy(sample_request())


def test_missing_api_key_maps_to_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend = OpenAICopyBackend()

    with pytest.raises(AdBackendError, match="OPENAI_API_KEY"):
        backend.generate_copy(sample_request())


@pytest.mark.parametrize(
    "exc, expected_status_code",
    [
        (
            openai.AuthenticationError("invalid key", response=_make_httpx_response(401), body=None),
            503,
        ),
        (
            openai.RateLimitError("rate limit", response=_make_httpx_response(429), body=None),
            503,
        ),
        (
            openai.BadRequestError("bad request", response=_make_httpx_response(400), body=None),
            422,
        ),
        (
            openai.ContentFilterFinishReasonError(),
            503,
        ),
        (
            openai.LengthFinishReasonError(completion=_make_chat_completion()),
            503,
        ),
    ],
)
def test_sdk_exceptions_map_to_backend_error(
    exc: Exception, expected_status_code: int
) -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=RaisingCompletions(exc))
    )
    backend = OpenAICopyBackend(model_id="gpt-test-mini", client=client)

    with pytest.raises(AdBackendError) as exc_info:
        backend.generate_copy(sample_request())

    assert exc_info.value.status_code == expected_status_code
