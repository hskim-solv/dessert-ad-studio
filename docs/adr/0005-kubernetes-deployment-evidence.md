# 0005. Kubernetes 배포 증거 패키지

- 날짜: 2026-06-13
- 상태: 채택됨
- 관련: ADR-0003(FLUX.2 검증 라운드), `deploy/k8s/`, `docs/evidence/k8s-deployment.md`

## 배경 (Context)

Dessert Ad Studio는 FastAPI API, Streamlit UI, Triton template scorer,
OpenTelemetry/OpenInference trace, Phoenix evidence를 이미 갖췄다. 다음 포트폴리오
증거는 "로컬에서 돌아간다"를 넘어 "운영 배포 형태로 설명하고 검증할 수 있다"는
Kubernetes 배포 가능성이다.

이번 결정은 실제 cloud cluster 운영을 도입하는 것이 아니라, 기존 Docker Compose
경로를 유지하면서 Kubernetes manifest와 재현 가능한 render evidence를 추가하는
범위다.

## 선택 기준 (Criteria)

- 채용 신호: Docker, Kubernetes, health check, autoscaling, ingress, observability를
  눈으로 확인 가능한 산출물로 제시할 수 있어야 한다.
- 구현 비용: cluster 상시 운영, Helm chart, KServe 같은 platform 도입은 과제 범위를
  넘기지 않아야 한다.
- 기존 구조 보존: FastAPI + Streamlit + Triton + Phoenix/OTLP 결정을 흔들지 않아야
  한다.
- 검증 가능성: 개인 로컬 환경에서도 `kubectl kustomize`와 focused tests로 evidence를
  남길 수 있어야 한다.
- 확장성: GKE/kind/minikube로 승격할 때 base/overlay 구조를 그대로 재사용할 수 있어야
  한다.

## 후보 비교 (Comparison)

| 기준 | Raw Kustomize manifests (채택) | Helm chart | KServe/Ray Serve/BentoML |
|---|---|---|---|
| 구현 비용 | 낮음 | 중간 | 높음 |
| 채용 신호 | K8s primitives를 직접 보여줌 | 운영 패키징 신호는 좋음 | ML platform 신호는 강함 |
| 기존 구조 보존 | 높음 | 높음 | 중간 이하 |
| 로컬 검증 | `kubectl kustomize`로 쉬움 | Helm 설치 필요 | cluster/operator 필요 |
| 과잉 설계 위험 | 낮음 | 중간 | 높음 |

## 결정 (Decision)

Kubernetes 배포 증거는 **raw Kustomize manifests**로 유지한다.

기본 경로는 `deploy/k8s/base`에 API, Streamlit, Triton, PVC, Ingress, HPA를 둔다.
선택 경로는 overlay로 분리한다.

- `deploy/k8s/overlays/gpu`: Triton GPU node pool 증거
- `deploy/k8s/overlays/agentops`: API -> OTEL Collector -> Phoenix trace evidence

OpenTelemetry Collector는 Kubernetes 공식 운용 패턴에 맞춰 OTLP receiver,
`k8sattributes` processor, `batch` processor를 사용한다. 앱은 collector의 OTLP HTTP
endpoint로 trace를 보내고, collector가 Phoenix OTLP HTTP traces endpoint로 전달한다.

AgentOps overlay의 Phoenix 저장소는 `/phoenix_data` `emptyDir`이다. 따라서 retention은
Phoenix pod lifetime으로 제한되고, scope는 `dessert-ad-studio` namespace의 local/demo
workflow traces다. 실제 고객 이미지, 원문 prompt, 생성 결과 바이너리처럼 민감한 payload를
trace에 장기 저장하는 용도가 아니다.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - Helm chart, KServe, Ray Serve 같은 고수준 platform 증거는 아직 없다.
  - live cluster screenshot은 별도 kind/minikube/GKE 라운드가 필요하다.
  - Phoenix overlay는 local evidence 목적이므로 production에서는 image tag pinning,
    persistent storage, auth/network policy, trace redaction을 재검토해야 한다.
- 재평가 트리거:
  - GKE나 EKS 배포를 실제로 수행할 때 Helm packaging 또는 GitOps overlay를 추가한다.
  - GPU image serving을 상시 운영할 때 node selector/toleration, NVIDIA device plugin,
    model sync job을 별도 ADR로 승격한다.
  - traffic/load evidence가 필요할 때 Prometheus/Grafana 또는 managed monitoring을
    추가한다.

## Primary References

- Kubernetes probes:
  https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Kubernetes HPA:
  https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/
- Kubernetes Ingress:
  https://kubernetes.io/docs/concepts/services-networking/ingress/
- OpenTelemetry Kubernetes Collector components:
  https://opentelemetry.io/docs/platforms/kubernetes/collector/components/
