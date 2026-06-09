from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper


def build_model() -> onnx.ModelProto:
    features = helper.make_tensor_value_info("features", TensorProto.FLOAT, [None, 8])
    scores = helper.make_tensor_value_info("scores", TensorProto.FLOAT, [None, 4])

    weights = np.array(
        [
            [0.9, 0.4, 0.7, 0.5],
            [0.2, 0.3, 0.5, 1.0],
            [0.5, 0.5, 0.8, 0.6],
            [0.6, 0.8, 0.4, 0.5],
            [0.9, 0.3, 0.7, 0.8],
            [0.4, 1.0, 0.2, 0.5],
            [0.5, 0.2, 1.0, 0.7],
            [0.7, 0.9, 0.4, 0.5],
        ],
        dtype=np.float32,
    )
    bias = np.array([0.05, 0.05, 0.05, 0.05], dtype=np.float32)

    graph = helper.make_graph(
        nodes=[
            helper.make_node("MatMul", ["features", "weights"], ["raw_scores"]),
            helper.make_node("Add", ["raw_scores", "bias"], ["biased_scores"]),
            helper.make_node("Sigmoid", ["biased_scores"], ["scores"]),
        ],
        name="template_scorer",
        inputs=[features],
        outputs=[scores],
        initializer=[
            numpy_helper.from_array(weights, name="weights"),
            numpy_helper.from_array(bias, name="bias"),
        ],
    )
    model = helper.make_model(graph, producer_name="dessert-ad-studio")
    onnx.checker.check_model(model)
    return model


def main() -> None:
    output_path = Path("models/template_scorer/1/model.onnx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(build_model(), output_path)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
