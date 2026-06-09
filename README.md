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

## Docker Compose demo

Generate the ONNX model before starting Triton:

```bash
python scripts/export_template_scorer_onnx.py
docker compose up --build
```

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
