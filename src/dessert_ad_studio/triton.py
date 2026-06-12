from __future__ import annotations

from time import perf_counter

import numpy as np

from dessert_ad_studio.prompts import template_features
from dessert_ad_studio.schemas import GenerationRequest, TemplateHint, TemplateRanking

TEMPLATES: tuple[TemplateHint, ...] = (
    "cozy_cafe",
    "minimal_premium",
    "cute_dessert",
    "seasonal_event",
)


class LocalTemplateScorer:
    def rank(self, request: GenerationRequest) -> TemplateRanking:
        started = perf_counter()
        features = np.array(template_features(request), dtype=np.float32)
        weights = np.array(
            [
                [0.9, 0.2, 0.5, 0.6, 0.9, 0.4, 0.5, 0.7],
                [0.4, 0.3, 0.5, 0.8, 0.3, 1.0, 0.2, 0.9],
                [0.7, 0.5, 0.8, 0.4, 0.7, 0.2, 1.0, 0.4],
                [0.5, 1.0, 0.6, 0.5, 0.8, 0.5, 0.7, 0.5],
            ],
            dtype=np.float32,
        )
        scores = weights @ features
        best_index = int(np.argmax(scores))
        normalized = float(1.0 / (1.0 + np.exp(-scores[best_index])))
        elapsed_ms = (perf_counter() - started) * 1000
        return TemplateRanking(
            template_name=TEMPLATES[best_index],
            score=normalized,
            scorer="local-template-scorer",
            latency_ms=elapsed_ms,
        )


class TritonTemplateScorer:
    def __init__(self, url: str = "localhost:8000") -> None:
        self.url = url

    def rank(self, request: GenerationRequest) -> TemplateRanking:
        import tritonclient.http as httpclient

        started = perf_counter()
        client = httpclient.InferenceServerClient(url=self.url)
        features = np.array([template_features(request)], dtype=np.float32)
        infer_input = httpclient.InferInput("features", features.shape, "FP32")
        infer_input.set_data_from_numpy(features)
        output = httpclient.InferRequestedOutput("scores")
        response = client.infer("template_scorer", [infer_input], outputs=[output])
        scores = response.as_numpy("scores")[0]
        best_index = int(np.argmax(scores))
        elapsed_ms = (perf_counter() - started) * 1000
        return TemplateRanking(
            template_name=TEMPLATES[best_index],
            score=float(scores[best_index]),
            scorer="triton-template-scorer",
            latency_ms=elapsed_ms,
        )
