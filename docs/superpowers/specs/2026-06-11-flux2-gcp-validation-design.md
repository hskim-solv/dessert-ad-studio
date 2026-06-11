# FLUX.2 GCP L4 검증 라운드 — 설계

- 날짜: 2026-06-11
- 상태: 사용자 승인됨 (구현 계획 작성 전)
- 관련: ADR-0002 (FLUX.2 헤지·i2i 리스크), 작성 예정 ADR-0003

## 1. 배경과 목표

flux2 이미지 백엔드는 슬롯(어댑터·팩토리·환경변수)만 준비된 미검증 상태다. 이 라운드는 GCP L4 GPU VM에서 `IMAGE_BACKEND=flux2`로 실제 이미지 생성을 1회 검증하고, 그 과정을 컨테이너 기반 GPU 서빙 + 추론 텔레메트리라는 재사용 가능한 산출물로 남긴다.

배경 제약: 코스 제공 VM이 아닌 **개인 유료 GCP 계정**(GPU 쿼터 미확인)을 사용하므로 실비가 과금된다. 또한 사용자의 커리어 타깃 JD(AI 서비스 백엔드 — Docker/K8s 필요 역량, inference 성능·비용 최적화, Triton 등 로컬 모델 서빙 우대)가 채택 기준에 포함된다.

## 2. 확정된 결정 (사용자 승인)

| 결정 | 선택 | 핵심 근거 |
|---|---|---|
| 성공 기준 | 1회 검증 데모 후 VM 정지 | 최소 비용 (~$2–3), 재현 스크립트로 재기동 가능 |
| 실행 방식 | gcloud CLI 로컬 설치 + Claude 원격 자동화 | 사용자 개입은 `gcloud auth login` 1회 |
| 배포 경로 | Docker Compose + GPU 오버레이 | venv 직접 실행 대비 +30–60분이지만 JD 필요 역량(컨테이너 GPU 서빙)의 증거 산출 |
| 모델 변형 | `black-forest-labs/FLUX.2-klein-4B` | 아래 실측 근거 — 라이선스·게이트·VRAM 모두 유일하게 무리 없음 |
| 텔레메트리 | 생성 latency·스텝·VRAM peak를 usage로 기록 | JD의 "inference 성능·비용 최적화" 증거 + 이후 최적화의 기준선 |

비교표 전문과 재평가 트리거는 ADR-0003에 기록한다 (산출물 §9).

## 3. 실측 근거 (2026-06-11, HF Hub API·PyPI 직접 조회)

- `black-forest-labs/FLUX.2-klein`(현 코드 기본값)은 **HF Hub에 존재하지 않음** → 차단급.
- `FLUX.2-klein-4B`: **gated: False, apache-2.0** (HF_TOKEN 불필요, 상업 광고 용도 적합), likes 719.
- `FLUX.2-klein-9B` / `FLUX.2-dev`: gated: auto + `license: other`(비상업 계열) → 광고 생성 용도 부적합, 제외.
- klein-4B `model_index.json`: 파이프라인 `Flux2KleinPipeline`, `is_distilled: true`, `_diffusers_version: 0.37.0.dev0`, 텍스트 인코더 `Qwen3ForCausalLM`.
- 모델 카드 권장 생성 파라미터: **`guidance_scale=1.0`, `num_inference_steps=4`**, 1024×1024 — 현 코드의 28 steps / guidance 3.5는 distilled 모델에 부적합한 값.
- PyPI 최신: diffusers 0.38.0 (→ 하한 `>=0.37` 성립), transformers 5.11.0 (Qwen3 지원은 4.51부터 → 하한 `>=4.51`).

## 4. 완료 기준 (수락 조건)

1. GCP L4 VM에서 `docker compose`(GPU 오버레이)로 api 서비스가 기동되고 컨테이너 내부에서 `torch.cuda.is_available() == True`.
2. `POST /generate`(copy=mock, image=flux2)가 200을 반환하고 FLUX.2 생성 PNG가 `outputs/`에 생성됨.
3. `logs/generations.jsonl`에 `image_usage`(generation_seconds, num_inference_steps, vram_peak_gb)가 채워진 행이 기록됨.
4. 증빙(PNG + JSONL 행)이 로컬 `outputs/gcp-validation/`으로 회수됨.
5. VM이 정지(stopped) 상태로 종료됨.
6. 로컬 전체 테스트(기존 66 + 신규 flux2 테스트) 통과, `backend-contract-reviewer` 검토 통과.

## 5. 코드 변경 명세 (전부 로컬 TDD, VM 과금 전 완료)

### 5.1 `src/dessert_ad_studio/backends/flux2.py`
- 기본 모델 id: `black-forest-labs/FLUX.2-klein-4B` (환경변수 `FLUX2_MODEL_ID` 오버라이드 유지).
- 생성 파라미터 기본값: 1024×1024, `num_inference_steps=4`, `guidance_scale=1.0` (모델 카드 권장).
- `AdBackendError` 매핑 (모두 한국어 detail, status_code 503):
  - 의존성 미설치(ImportError): "FLUX.2 백엔드 의존성이 설치되지 않았습니다. `pip install -e '.[image]'`로 설치해주세요."
  - 모델 로드 실패(`from_pretrained` 예외): "FLUX.2 모델 로드에 실패했습니다: {원인}"
  - 추론 실패(pipeline 호출 예외, OOM 포함): "FLUX.2 이미지 생성에 실패했습니다: {원인}"
- 텔레메트리: `ImageResult.usage = {"generation_seconds": float, "num_inference_steps": int, "vram_peak_gb": float | None}` — 시간은 `time.monotonic`, VRAM은 `torch.cuda.max_memory_allocated()`(CUDA 없으면 None). 기존 JSONL `image_usage` 경로로 자동 기록되므로 api/main.py 변경 불요.
- 기존 계약 유지: frozen `ImageResult`, lazy import, `supports_reference_image = False`, 무상태(텔레메트리는 반환값으로만 전달).

### 5.2 `pyproject.toml`
- `[image]`: `diffusers>=0.37`, `transformers>=4.51`로 상향 (나머지 유지).

### 5.3 Docker
- `Dockerfile.api`: build arg `INSTALL_IMAGE_EXTRAS`(기본 0) 추가 — 1이면 `pip install -e ".[image]"`. CPU 로컬 데모 이미지는 기존처럼 가볍게 유지.
- `docker-compose.gpu.yml` 신설 (오버레이로만 사용, 기본 compose 동작 불변):
  - api: build arg `INSTALL_IMAGE_EXTRAS=1`, `IMAGE_BACKEND=flux2`, `FLUX2_MODEL_ID` 패스스루, `HF_HOME=/data/hf-cache`, **`REQUIRE_TRITON=0`** (기본 compose의 1을 덮어 LocalTemplateScorer 폴백 — Triton 컨테이너 없이 api 단독 검증 가능).
  - GPU 예약: `deploy.resources.reservations.devices` (driver nvidia, count 1, capabilities [gpu]).
  - named volume `hf-cache` → 모델(~8GB) 재다운로드 방지.

### 5.4 테스트 — `tests/test_flux2_backend.py` 신설 (mock 기반, GPU/torch 불필요)
- import 실패 → `AdBackendError` 한국어 detail + 503.
- 파이프라인 로드 실패 → `AdBackendError`.
- 추론 실패 → `AdBackendError`.
- 정상 mock 경로 → `ImageResult` 반환, 경로가 output_dir 내부(traversal 안전), usage 키 3종 존재.
- `supports_reference_image is False`.
- 기존 test_api.py의 flux2 reference 거부 2건은 회귀 유지.

### 5.5 기타
- `scripts/flux2_smoke.py`: 백엔드 직접 호출로 1장 생성(openai_smoke.py 패턴) — VM에서 API 기동 전 1차 검증용.
- `.env.example`: `FLUX2_MODEL_ID=black-forest-labs/FLUX.2-klein-4B`로 갱신.
- README: GPU 오버레이 실행법 + [image] extras 설치 한 줄.

## 6. GCP 인프라 절차 (gcloud 자동화)

1. 로컬 `brew install --cask google-cloud-sdk` → 사용자가 `! gcloud auth login` 1회 (계정 times21c@gmail.com).
2. 프로젝트 확인/생성, 결제 연결 확인.
3. GPU 쿼터 확인 (`GPUS_ALL_REGIONS`, 리전별 `NVIDIA_L4_GPUS`). 0이면 사용자 콘솔 증설 요청 후 대기(보통 분–시간 단위).
4. VM 생성: `g2-standard-4`(L4 1개 포함; 코스 가이드와 동일 사양이라 코스 VM에도 절차 이식 가능), 리전 us-central1(쿼터 승인 리전 우선), 부트 디스크 80GB, 이미지 `ubuntu-accelerator-2204-amd64-with-nvidia-550`(NVIDIA 드라이버 사전 설치).
5. VM에 Docker Engine + docker compose plugin + nvidia-container-toolkit 설치(스크립트화하여 repo에 커밋).
6. 비용 가드: 단계별 타임박스, 실패 시 즉시 `gcloud compute instances stop`, 세션 종료 시 정지 확인. 예상 총비용 ~$2–3 (시간당 ~$0.85 × 2–3h).

## 7. VM 검증 절차 (원격 자동화, 단계별 검증 후 진행)

1. 코드 전송: `git bundle` 생성 → `gcloud compute scp` → VM에서 clone (VM에 GitHub 인증 불필요).
2. `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d --no-deps api` — `--no-deps`로 `depends_on: triton`을 차단해 Triton 이미지(~10GB+) 다운로드를 회피 (오버레이의 `REQUIRE_TRITON=0`이 LocalTemplateScorer 폴백을 보장; triton/app 컨테이너는 이번 검증 범위 밖).
3. 컨테이너 내 `python -c "import torch; print(torch.cuda.is_available())"` → True 확인.
4. `scripts/flux2_smoke.py` (컨테이너 내) → 1장 생성 + 소요 시간 확인 (klein-4B 4 steps라 수 초–수십 초 예상; 최초 실행은 모델 다운로드 ~8GB 포함).
5. `curl POST /generate` (copy=mock) → 200 + PNG + JSONL `image_usage` 행 확인.
6. 증빙 회수: PNG + JSONL을 로컬 `outputs/gcp-validation/`으로 scp.
7. `docker compose down` → VM stop → 정지 상태 확인.

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| GPU 쿼터 0/거부 | 타 리전(us-east1 등) 재시도 → 그래도 거부면 사용자 콘솔 요청 안내 후 일시 중단 |
| RAM 16GB에서 로드 OOM | klein-4B(~8GB bf16)로 마진 확보. 발생 시 `low_cpu_mem_usage` 확인 |
| 이미지 빌드 시간 | torch 설치 레이어를 분리해 재빌드 캐시 활용 |
| 모델 다운로드 중단 | HF 캐시 볼륨으로 이어받기, 재시도 |
| 과금 누수 | 모든 실패 경로에서 즉시 VM stop, 마지막 단계에서 정지 상태 재확인 |

## 9. 산출물

- 코드 변경(§5) + 신규 테스트 — PR로 머지.
- `docs/runbooks/gcp-flux2-validation.md`: VM 생성→검증→정지 전 절차 (재실행 가능 명령 포함).
- ADR-0003: 모델 변형 비교표(klein-4B/9B/dev — 라이선스·VRAM·게이트), 배포 경로 비교표(venv/Docker GPU — JD 정합 기준 포함), 텔레메트리 채택, Triton 재평가 각주(ADR-0002 결정 1의 "과제 종료 후 onnxruntime 간소화 권고"는 JD의 Triton 우대로 재고 대상).
- 검증 증빙: `outputs/gcp-validation/` (PNG + JSONL 발췌) — 보고서/발표 자료의 원천.

## 10. 범위 밖 (보류, 트리거와 함께)

- i2i(reference 이미지) 파이프라인: 기존 ADR-0002 트리거 유지 (OpenAI 사용량 80% 도달 시).
- 발표용 풀스택 상시 데모(Streamlit 포함 기동·정지 runbook): 라이브 시연 일정 확정 시.
- GKE/K8s 서빙: 후속 라운드 후보 — JD 정합상 가치 있으나 이번 검증 범위 아님.
- seed 재현성·생성 파라미터 환경변수화: 필요 사례 등장 시 (YAGNI).
