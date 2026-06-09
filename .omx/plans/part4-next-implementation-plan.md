# Part4 next implementation plan

Use these source-of-truth documents:

- `docs/superpowers/specs/2026-06-09-cafe-dessert-reference-template-ad-generator-design.md`
- `docs/reference/class-materials-alignment.md`

Course-material-aligned implementation order:

1. Initialize project skeleton and README.
2. Build Streamlit mock UI first, aligned with notebook 4-3.
3. Implement prompt/template engine and structured generation logs.
4. Add FastAPI backend boundary, aligned with notebook 4-4.
5. Add ONNX `template_scorer` export and Triton model repository, aligned with notebooks 4-2 and 4-5.
6. Connect FastAPI to Triton and make template ranking part of the normal generation path.
7. Connect Streamlit to FastAPI using mock copy/image generation.
8. Add image-generation adapter interface.
9. Implement one reliable image backend, with FLUX.2 as the primary modern local target and API/mock fallback for demo reliability.
10. Add one advanced control path through reference/template conditioning; use SDXL ControlNet/IP-Adapter only as fallback if FLUX.2 control support is unstable.
11. Add Dockerfile, docker-compose, and smoke commands, aligned with notebook 4-1.
12. Add evaluation/report artifacts: Triton latency, image latency, controllability examples, prompt-fit samples, UI flow screenshots.

Immediate scaffold target:

- `app/streamlit_app.py`
- `src/dessert_ad_studio/prompts.py`
- `src/dessert_ad_studio/logging.py`
- `src/dessert_ad_studio/backends/mock.py`
- `src/dessert_ad_studio/triton.py`
- `models/template_scorer/config.pbtxt`
- `scripts/export_template_scorer_onnx.py`
- `scripts/triton_smoke.py`
- `api/main.py`
- `tests/`
- `README.md`
- `.env.example` and `.gitignore`

Stop condition before real API/model calls: skeleton, mock flow, ONNX export script, and Triton smoke path are documented and locally testable.
