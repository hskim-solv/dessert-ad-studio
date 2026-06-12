from __future__ import annotations

import os

import numpy as np
import tritonclient.http as httpclient


def main() -> None:
    url = os.getenv("TRITON_URL", "localhost:8000")
    client = httpclient.InferenceServerClient(url=url)
    assert client.is_server_ready(), "Triton server is not ready"
    assert client.is_model_ready("template_scorer"), "template_scorer is not ready"

    features = np.array([[1, 0, 0, 0, 1, 0, 0, 0]], dtype=np.float32)
    infer_input = httpclient.InferInput("features", features.shape, "FP32")
    infer_input.set_data_from_numpy(features)
    output = httpclient.InferRequestedOutput("scores")
    response = client.infer("template_scorer", [infer_input], outputs=[output])
    scores = response.as_numpy("scores")

    assert scores.shape == (1, 4), f"unexpected score shape: {scores.shape}"
    print({"ready": True, "model": "template_scorer", "scores": scores.tolist()})


if __name__ == "__main__":
    main()
