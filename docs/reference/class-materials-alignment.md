# Part 4 Class Materials Alignment

Date: 2026-06-09
Project: Dessert Ad Studio

This document maps the provided Part 4 notebooks to the current project plan.

## Source notebooks

- `4-1.Docker컨테이너와 이미지, 쿠버네티스.ipynb`
- `4-2.딥러닝 모델 변환과 양자화.ipynb`
- `4-3.웹앱프레임워크를 활용하여 프로토타입 개발하기.ipynb`
- `4-4.FastAPI로 모델 서빙하기.ipynb`
- `4-5.모델 서빙 프레임워크로 모델 서빙하기.ipynb`

## How each notebook will be used

| Notebook | Project use | Priority |
| --- | --- | --- |
| 4-3 Streamlit prototype | Main MVP UI: upload images, select campaign/template/tone, generate copy/image, download output | Required first |
| 4-4 FastAPI serving | Backend boundary after UI works: `/generate-copy`, `/generate-image`, `/health`, request/response schemas | Required after mock UI |
| 4-1 Docker/Kubernetes | Reproducible deployment: Dockerfile, image build/run, optional GPU container notes | Required before final demo |
| 4-2 model conversion/quantization | Export the lightweight `template_scorer` helper model to ONNX and explain why full diffusion-model conversion is out of MVP scope | Required evidence |
| 4-5 model serving framework/Triton | Serve the ONNX `template_scorer` through Triton and call it from FastAPI before image generation | Required |

## Important implementation decision

The project is a generative image service. FLUX.2/Diffusers image generation is not as straightforward to convert to ONNX/Triton as a simple classifier. Therefore:

- The MVP must include Triton, but Triton should serve a bounded helper model instead of the full diffusion pipeline.
- The required Triton artifact is an ONNX `template_scorer` that ranks ad templates from structured campaign features.
- The main delivery path should be Streamlit + FastAPI + image-generation adapter.
- Docker should be used for reproducibility.
- FLUX.2 should be the primary modern image-generation target; SDXL is only a fallback/control ecosystem option.

## Updated build order

1. Initialize project skeleton and README.
2. Build Streamlit mock UI following the 4-3 prototype-first flow.
3. Add prompt/template engine and local generation logs.
4. Add FastAPI backend boundary following the 4-4 model-serving flow.
5. Add ONNX export script and Triton model repository for `template_scorer`.
6. Connect FastAPI to Triton and expose template ranking.
7. Connect Streamlit to FastAPI with mocked image generation.
8. Add reliable image backend adapter, with FLUX.2 as the primary local target.
9. Add Dockerfile, docker-compose, and smoke run commands following 4-1.
10. Add evaluation/report artifacts: Triton latency, image latency, controllability, prompt fit, UI flow.

## Presentation/report framing

Use the notebooks as the course-aligned technical backbone:

- 4-3 proves web prototype competence.
- 4-4 proves API serving competence.
- 4-1 proves deployment/reproducibility competence.
- 4-2 proves model export/optimization awareness through the ONNX `template_scorer`.
- 4-5 proves production serving-framework competence through required Triton inference.

## Verification checkpoints

- Streamlit app starts locally.
- FastAPI `/health` returns success.
- Triton `/v2/models/template_scorer/ready` returns success.
- FastAPI `/rank-templates` returns a Triton-backed ranking.
- Streamlit can call FastAPI mock endpoints.
- A generation request writes a structured log row.
- Docker image builds and runs at least the app shell.
- README documents the above commands.
