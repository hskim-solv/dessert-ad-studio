# 0003. FLUX.2 검증 라운드: 모델 변형·배포 경로·텔레메트리

- 날짜: 2026-06-11
- 상태: 채택됨
- 관련: ADR-0002(FLUX.2 헤지), spec `docs/superpowers/specs/2026-06-11-flux2-gcp-validation-design.md`

## 배경 (Context)

flux2 백엔드를 GCP L4 VM에서 실검증하는 라운드. 선택 기준에 과제 요건 외에
**포트폴리오 가치(AI 서비스 백엔드 JD 정합: Docker/K8s, inference 성능·비용
최적화, 로컬 모델 서빙)**를 포함한다. 비용은 개인 유료 계정 실비.

## 선택 기준 (Criteria)

- 라이선스·게이트: 상업 광고 생성 용도 적합 + HF_TOKEN 없이 재현 가능해야 함
- 자원 적합성: L4 24GB VRAM / g2-standard-4 16GB RAM에서 무리 없이 동작
- 재현성: VM을 지워도 compose 파일·스크립트로 동일 환경 재구성 가능
- 포트폴리오 가치: JD 필요·우대 역량(컨테이너 GPU 서빙, inference 텔레메트리)의 직접 증거
- 구현 비용: 1회 검증 데모 목표 대비 과잉 설계 회피 (YAGNI)

## 결정 1: 모델 변형 — FLUX.2-klein-4B

기존 기본값 `black-forest-labs/FLUX.2-klein`은 HF Hub에 **공개(비게이트) repo로
존재하지 않았다**(2026-06-11 Hub API 확인). 실재 변형 비교:

| 기준 | klein-4B (채택) | klein-9B | FLUX.2-dev |
|---|---|---|---|
| 게이트 | 없음 (gated: False) | gated: auto | gated: auto |
| 라이선스 | apache-2.0 (상업 광고 OK) | other (비상업 계열) | other (비상업 계열) |
| bf16 VRAM (대략) | ~8GB 가중치 — L4 24GB 여유 | ~18GB — 빠듯 | 24GB+ — 불가 |
| 권장 생성 | 4 steps / guidance 1.0 (distilled) | 동일 계열 | 50 steps급 |
| 16GB RAM 로드 | 여유 | 위험 | 불가 |

광고 생성 용도(상업)에서 라이선스·게이트·VRAM 모두 무리 없는 변형은 klein-4B뿐.
생성 파라미터도 distilled 권장값(4 steps, guidance 1.0)으로 교정했다.

## 결정 2: 배포 경로 — Docker Compose GPU 오버레이

| 기준 | venv 직접 실행 | Docker GPU 오버레이 (채택) |
|---|---|---|
| 검증까지 추가 시간 | 0 | +30–60분 (toolkit, 빌드) |
| 재현성 | VM 로컬 상태 의존 | compose 파일로 고정 |
| 로컬 CPU 데모 영향 | 없음 | 없음 (오버레이 분리) |
| 포트폴리오 가치 | 낮음 | 높음 — JD 필요 역량(컨테이너 GPU 서빙) 직접 증거 |

JD 정합 기준이 없었다면 venv가 합리적이나(실제로 1차 선택), 사용자 커리어 타깃
반영으로 Docker 경로를 채택. `INSTALL_IMAGE_EXTRAS` build arg로 CPU 이미지는
기존처럼 가볍게 유지한다.

## 결정 3: 추론 텔레메트리 — ImageResult.usage로 반환

| 기준 | 기록 안 함 | usage 반환값 (채택) | 별도 미들웨어/APM |
|---|---|---|---|
| 백엔드 무상태 계약 | — | 유지 (반환값 전달) | 유지 |
| 구현 비용 | 0 | 소 (기존 JSONL 경로 재사용) | 대 |
| JD 증거 (inference 성능·비용) | 없음 | 기준선 수치 확보 | 과잉 |

`generation_seconds`(time.monotonic) / `num_inference_steps` / `vram_peak_gb`
(torch.cuda.max_memory_allocated)를 기록 — 이후 최적화(스텝 수, dtype, 배치)의
전/후 비교 기준선이 된다.

한계: `vram_peak_gb`는 전역 CUDA 카운터 기반의 **단일 추론 근사치**다 — 동시
생성 요청이 겹치면 서로의 peak이 교차 오염될 수 있다. 단일 요청 검증·기준선
용도로는 충분하며, 동시성 환경의 정밀 계측이 필요해지면 per-request 측정으로
재설계한다.

## 실측 결과 (2026-06-11, L4, 1024x1024, 4 steps)

| 지표 | 값 |
|---|---|
| generation_seconds (스모크 / API 경유) | 5.26 / 4.85 |
| vram_peak_gb | 17.32 |

전체 절차·부가 실측치(빌드 시간, 다운로드 시간, 비용)는
`docs/runbooks/gcp-flux2-validation.md` 참조.

## 각주: Triton 재평가

ADR-0002 결정 1의 "과제 종료 후 onnxruntime 간소화 권고"는 JD의 Triton 서빙
우대를 반영해 보류한다. Triton 경로는 포트폴리오 가치가 있으므로 과제 종료
시점에 재평가한다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것: GPU 오버레이 경로의 빌드 시간(실측 7분 20초),
  klein-4B의 한글 텍스트 렌더링 한계(비문 — 텍스트는 후처리 오버레이 필요),
  vram_peak_gb의 동시성 한계(위 결정 3).
- 재평가 트리거:
  - i2i(reference 이미지) 요구 확정 시: klein-4B의 i2i 파이프라인 지원 재조사
    (ADR-0002 트리거와 동일).
  - klein-9B/dev 라이선스가 상업 허용으로 바뀌거나 게이트가 풀리면 품질 비교 재실시.
  - 상시 데모/대규모 트래픽 요구 발생 시: K8s(GKE) 서빙 라운드로 승격.
