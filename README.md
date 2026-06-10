# Dessert Ad Studio

Cafe/dessert ad-generation prototype for small business owners.

## MVP flow

1. User enters campaign purpose, tone, product name, and style preferences in Streamlit.
2. Streamlit calls FastAPI.
3. FastAPI renders prompts and calls Triton `template_scorer`.
4. FastAPI returns three Korean ad-copy candidates and one SNS-ready image path.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run tests

```bash
pytest -q
```

## Run API

```bash
uvicorn api.main:app --reload --port 8000
```

## Run Streamlit

```bash
streamlit run app/streamlit_app.py
```

## Export Triton model

```bash
python scripts/export_template_scorer_onnx.py
```

## Triton smoke flow

```bash
docker compose up triton -d
python scripts/triton_smoke.py
```

The default local Triton image is the smaller full server tag
`nvcr.io/nvidia/tritonserver:22.12-py3`. Override it on a larger VM if needed:

```bash
TRITON_IMAGE=nvcr.io/nvidia/tritonserver:24.05-py3 docker compose up triton -d
```

## Configuration

Copy `.env.example` to `.env` and edit local values. Do not commit `.env`.

### Generation backends

Copy and image generation switch independently:

| Variable | Values | Default |
| --- | --- | --- |
| `COPY_BACKEND` | `mock`, `openai` | `mock` |
| `IMAGE_BACKEND` | `mock`, `openai`, `flux2` | `mock` |
| `COPY_MODEL_ID` | any chat model id | `gpt-5.4-mini` |
| `IMAGE_MODEL_ID` | any GPT image model id | `gpt-image-1-mini` |
| `IMAGE_QUALITY` | `low`, `medium`, `high` | `low` |

Real backends need `OPENAI_API_KEY` in `.env`. Uploading a reference image in
Streamlit switches the OpenAI image backend from text-to-image to edit mode.
Keep `IMAGE_QUALITY=low` while iterating; raise it only for final demo shots.

### OpenAI smoke check (manual, costs quota)

After pulling this branch, re-run `pip install -e ".[dev]"` once (it adds the `openai` dependency).

```bash
python scripts/openai_smoke.py                      # copy + text-to-image
python scripts/openai_smoke.py my_product_photo.jpg # copy + reference edit
```

Run it once after setting a key to confirm the configured model ids exist and
to record baseline latency/token usage. It is intentionally not part of pytest.

## Docker Compose demo

Generate the ONNX model before starting Triton:

```bash
python scripts/export_template_scorer_onnx.py
docker compose up --build
```

To use `openai` backends in the compose demo, put `OPENAI_API_KEY` (and any backend overrides) in `.env` beside `docker-compose.yml`; Compose reads it automatically.

Open Streamlit:

```text
http://localhost:8501
```

FastAPI is exposed on:

```text
http://localhost:8080
```

Triton HTTP is exposed on:

```text
http://localhost:8001
```
