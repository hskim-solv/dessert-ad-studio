# 0010. Kubernetes 라이브 배포 스모크 경로

- 날짜: 2026-06-17
- 상태: 채택됨
- 관련: `scripts/k8s_live_smoke.py`, `deploy/k8s/`, `docs/evidence/k8s-deployment.md`, ADR-0005

## 배경 (Context)

적대적 포트폴리오 리뷰에서 Kubernetes 증거가 `kubectl kustomize` render
검증에 머물러 있고, 실제 pod scheduling과 API traffic smoke가 없다는 지적이
나왔다.

이번 결정은 새로운 상시 클러스터나 cloud 비용을 도입하지 않고, 로컬/테스트
Kubernetes context에서만 fail-closed로 live smoke를 실행할 수 있는 경로를
추가하는 것이다. 실제 live run은 `kind`, `minikube`, `docker-desktop`,
`rancher-desktop`, `k3d-*` 같은 로컬 context가 준비된 경우에만 수행한다.

## 선택 기준 (Criteria)

- 안전성: 실수로 production cluster에 `kubectl apply`하지 않아야 한다.
- 재현성: reviewer가 이미 가진 로컬 Kubernetes context에서 같은 command를
  실행할 수 있어야 한다.
- 추가 의존성 최소화: 새로운 cluster manager를 강제 설치하지 않아야 한다.
- 증거 가치: apply, rollout, port-forward, API smoke, summary artifact를 남겨
  render evidence보다 강한 proof로 확장 가능해야 한다.
- 확장성: 나중에 kind/minikube/k3d 자동 생성이나 worker/Redis/Postgres overlay를
  붙여도 기존 스모크 계약을 유지해야 한다.

## 후보 비교 (Comparison)

| 기준 | 기존 `kubectl` context + fail-closed smoke (채택) | kind 전용 자동 클러스터 | minikube 전용 자동 클러스터 | k3d 전용 자동 클러스터 |
|---|---|---|---|---|
| 안전성 | context allowlist로 production 오적용 차단 | 좋음, 별도 cluster 생성 | 좋음, 별도 cluster 생성 | 좋음, 별도 cluster 생성 |
| 추가 의존성 | `kubectl`만 필요 | `kind` 설치 필요 | `minikube` 설치 필요 | `k3d` 설치 필요 |
| Docker Desktop 의존 | 선택적 | 필요 | driver별 상이 | 필요 |
| CI/로컬 재현성 | 사용자가 가진 context에 맞춤 | 좋음 | 중간 | 좋음 |
| 구현 비용 | 낮음 | 중간 | 중간 이상 | 중간 |
| 포트폴리오 증거 | apply/rollout/API smoke까지 확장 | local cluster proof까지 강함 | local cluster proof까지 강함 | local cluster proof까지 강함 |

## 결정 (Decision)

`scripts/k8s_live_smoke.py`를 추가해 **기존 `kubectl` context 기반의
fail-closed live smoke**를 채택한다.

기본 허용 context는 다음 로컬/테스트 계열이다.

- `kind-*`
- `minikube`
- `docker-desktop`
- `rancher-desktop`
- `k3d-*`

script는 다음 순서로 실행한다.

1. `kubectl config current-context` 확인.
2. context allowlist 검증. 허용되지 않으면 apply 전 실패.
3. `kubectl apply -k deploy/k8s/base`.
4. `deploy/api`, `deploy/app`, `deploy/triton` rollout status 확인.
5. `svc/api` port-forward.
6. 기존 `scripts/api_smoke.py`의 API smoke 실행.
7. redacted JSON summary 작성.

## 결과 및 재평가 조건 (Consequences)

- 이 선택으로 감수하는 것:
  - 현재 machine에 local Kubernetes context가 없으면 live proof는 실행되지 않는다.
  - 이 script는 cluster를 생성하지 않는다.
  - 현재 base manifest는 worker/Redis/Postgres async path를 포함하지 않는다.
  - Triton model PVC sync는 아직 별도 단계다.
- 재평가 트리거:
  - 이 machine 또는 CI에 `kind`를 설치해 disposable cluster proof를 자동화할 때
    kind bootstrap script를 추가한다.
  - Kubernetes에서 async job path까지 증명해야 할 때 worker/Redis/Postgres overlay를
    별도 ADR 또는 ADR update로 추가한다.
  - production cluster smoke가 필요해질 때 image registry pinning, TLS, auth,
    network policy, secret management를 별도 hardening milestone로 승격한다.
