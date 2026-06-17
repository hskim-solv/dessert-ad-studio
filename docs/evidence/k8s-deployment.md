# Kubernetes Deployment Evidence

Date: 2026-06-13
Updated: 2026-06-17 live `kind` smoke

## Purpose

This note records deployment evidence for Dessert Ad Studio's Kubernetes path.
It complements the Docker Compose and Phoenix AgentOps evidence by showing that
the service can be rendered as a Kubernetes stack with health probes,
autoscaling, ingress, Triton model serving, and optional in-cluster trace
collection.

## Implemented Surface

- Base Kustomize stack under `deploy/k8s/base`.
- FastAPI Deployment and Service with `/livez` and `/readyz` probes.
- Streamlit Deployment and Service with `/_stcore/health` probes.
- Triton Deployment and Service with `/v2/health/live` and `/v2/health/ready`
  probes.
- Resource requests/limits for API, Streamlit, Triton, Phoenix, and OTEL
  Collector.
- API HorizontalPodAutoscaler using `autoscaling/v2`.
- Shared output/log PVC configured as `ReadWriteOnce` so local/test clusters
  such as `kind` can provision it with the default local-path storage class.
- NGINX Ingress with host-based UI/API routing.
- GPU overlay for Triton GPU scheduling evidence.
- AgentOps overlay with API -> OpenTelemetry Collector -> Phoenix trace routing.

## Local Render Verification

Base stack:

```bash
kubectl kustomize deploy/k8s/base >/tmp/dessert-k8s-base.yaml
```

Result:

```text
render_all=passed
base_docs=12
hpa=True
startup_probe=True
resources=True
ingress_class=True
rwo_outputs=True
```

GPU overlay:

```bash
kubectl kustomize deploy/k8s/overlays/gpu >/tmp/dessert-k8s-gpu.yaml
```

Result:

```text
render_all=passed
gpu_request=True
doc_count=12
```

AgentOps overlay:

```bash
kubectl kustomize deploy/k8s/overlays/agentops >/tmp/dessert-k8s-agentops.yaml
```

Result:

```text
render_all=passed
phoenix_deployment=True
otel_collector_deployment=True
api_otlp_endpoint=True
k8sattributes=True
phoenix_traces_endpoint=True
doc_count=20
```

## AgentOps Retention and Scope

The AgentOps overlay is for local/demo evidence.

- Storage location: Phoenix writes to `/phoenix_data` backed by pod-local
  `emptyDir`.
- Retention: traces live for the Phoenix pod lifetime and are removed when the
  pod is deleted.
- Scope: traces are limited to the `dessert-ad-studio` namespace and
  `dessert-ad-studio-api` service path.
- Sensitive data boundary: do not enable this overlay for real customer inputs
  until trace attributes have been reviewed for raw prompts, uploaded reference
  images, generated image outputs, and other payloads that should not be
  persisted.

Structural YAML checks:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import yaml

required = {
    "/tmp/dessert-k8s-base.yaml": {
        ("Deployment", "api"), ("Deployment", "app"),
        ("Deployment", "triton"), ("HorizontalPodAutoscaler", "api"),
        ("Ingress", "dessert-ad-studio"), ("PersistentVolumeClaim", "outputs"),
    },
    "/tmp/dessert-k8s-gpu.yaml": {("Deployment", "triton")},
    "/tmp/dessert-k8s-agentops.yaml": {
        ("Deployment", "api"), ("Deployment", "phoenix"),
        ("Deployment", "otel-collector"), ("Service", "otel-collector"),
        ("Service", "phoenix"), ("ConfigMap", "otel-collector-config"),
        ("Role", "otel-collector"), ("RoleBinding", "otel-collector"),
        ("ServiceAccount", "otel-collector"),
    },
}

for path, expected in required.items():
    docs = [doc for doc in yaml.safe_load_all(Path(path).read_text()) if doc]
    found = {(doc.get("kind"), doc.get("metadata", {}).get("name")) for doc in docs}
    missing = sorted(expected - found)
    if missing:
        raise SystemExit(f"{path} missing {missing}")
    ns_missing = [
        (doc.get("kind"), doc.get("metadata", {}).get("name"))
        for doc in docs
        if doc.get("kind") != "Namespace"
        and doc.get("metadata", {}).get("namespace") != "dessert-ad-studio"
    ]
    if ns_missing:
        raise SystemExit(f"{path} namespace_missing {ns_missing}")
    print(f"{Path(path).name}: docs={len(docs)} required=present namespace=present")

base = [doc for doc in yaml.safe_load_all(Path("/tmp/dessert-k8s-base.yaml").read_text()) if doc]
api = next(doc for doc in base if doc.get("kind") == "Deployment" and doc["metadata"]["name"] == "api")
assert "startupProbe" in api["spec"]["template"]["spec"]["containers"][0]
outputs = next(doc for doc in base if doc.get("kind") == "PersistentVolumeClaim" and doc["metadata"]["name"] == "outputs")
assert outputs["spec"]["accessModes"] == ["ReadWriteOnce"]
assert "nvidia.com/gpu" in Path("/tmp/dessert-k8s-gpu.yaml").read_text()
agentops_text = Path("/tmp/dessert-k8s-agentops.yaml").read_text()
for needle in [
    "http://otel-collector:4318/v1/traces",
    "k8sattributes:",
    "traces_endpoint: http://phoenix:6006/v1/traces",
]:
    assert needle in agentops_text, needle
print("structural_checks=passed")
PY
```

Result:

```text
dessert-k8s-base.yaml: docs=12 required=present namespace=present
dessert-k8s-gpu.yaml: docs=12 required=present namespace=present
dessert-k8s-agentops.yaml: docs=20 required=present namespace=present
structural_checks=passed
```

Docker Compose compatibility:

```bash
docker compose config -q
docker compose -f docker-compose.yml -f docker-compose.agentops.yml config -q
docker compose -f docker-compose.yml -f docker-compose.gpu.yml config -q
```

Result:

```text
compose_configs=passed
```

Focused regression tests:

```bash
.venv/bin/pytest tests/test_api.py tests/test_otel_trace_smoke.py tests/test_evaluation.py -q
```

Result:

```text
40 passed
```

OpenTelemetry smoke:

```bash
WORKFLOW_TRACING=otel WORKFLOW_TRACE_EXPORT=console .venv/bin/python scripts/otel_trace_smoke.py
```

Result:

```text
trace_smoke=passed export=console endpoint=local-console steps=7
```

## Render Evidence Proves

- The API, UI, Triton, Ingress, HPA, and AgentOps manifests render through
  Kubernetes-native Kustomize.
- API readiness is tied to `/readyz`; liveness is tied to `/livez`.
- Streamlit and Triton have service-specific probes instead of generic TCP-only
  checks.
- API autoscaling has CPU resource requests, which are required for CPU
  utilization based HPA behavior.
- The AgentOps overlay uses an in-cluster collector boundary instead of having
  application pods export directly to Phoenix.

## Live Smoke Path

Added on 2026-06-17:

```bash
.venv/bin/python scripts/k8s_live_smoke.py \
  --context kind-dessert-ad-studio \
  --kustomize-path deploy/k8s/base \
  --namespace dessert-ad-studio \
  --timeout 900 \
  --summary docs/evidence/k8s-live-smoke-summary.json
```

The script is intentionally fail-closed. By default it refuses to apply
manifests unless the active context looks local/test-scoped:

- `kind-*`
- `minikube`
- `docker-desktop`
- `rancher-desktop`
- `k3d-*`

When a safe context is available, the script applies the base Kustomize stack,
syncs `models/` into the `triton-models` PVC, restarts `deploy/triton`, waits
for `deploy/api`, `deploy/app`, and `deploy/triton`, port-forwards `svc/api`,
runs `scripts/api_smoke.py`, and writes a redacted summary to
`docs/evidence/k8s-live-smoke-summary.json`.

Current machine status on 2026-06-17:

- `kubectl` is installed.
- Docker Desktop is running.
- `kind` v0.32.0 is installed.
- `kind-dessert-ad-studio` local/test context is available.
- `dessert-ad-studio-api:latest` and `dessert-ad-studio-app:latest` were built
  locally and loaded into the kind node.

Live smoke result:

```text
API smoke passed: http://127.0.0.1:18080
k8s_live_smoke=passed
context=kind-dessert-ad-studio
elapsed_ms=98406
skip_generate=false
kubectl_apply=true
triton_model_sync=true
rollout_api=true
rollout_app=true
rollout_triton=true
api_port_forward=true
api_smoke=true
```

Post-smoke pod state:

```text
api      1/1 Running
app      1/1 Running
triton   1/1 Running
```

Triton model load excerpt:

```text
| template_scorer | 1 | READY |
```

The redacted machine-readable summary is committed at
`docs/evidence/k8s-live-smoke-summary.json`.

## What This Proves

- The base stack applies to a real local Kubernetes cluster.
- `outputs` and `triton-models` PVCs bind under `kind`'s default local-path
  provisioner.
- `models/` is synced into the `triton-models` PVC and Triton loads
  `template_scorer` as `READY`.
- `deploy/api`, `deploy/app`, and `deploy/triton` reach rollout success.
- Port-forwarded API smoke passes with `skip_generate=false`, which exercises
  the `/generate` path through the Triton template scorer.

## What This Does Not Prove Yet

- The base `ReadWriteOnce` outputs PVC is local/test friendly but is not a
  multi-node artifact strategy. Production scaling should use object storage or
  a dedicated `ReadWriteMany` overlay/storage class.
- The live proof covers the synchronous API/UI/Triton base stack. It does not
  yet include the async worker/Redis/Postgres path demonstrated by Docker
  Compose.
- `kind` does not include metrics-server by default, so HPA rendering is proven
  but live CPU autoscaling behavior is not.
- Production hardening such as TLS, image registry pinning, auth, network policy,
  and secret management is intentionally deferred.

## Reproduction Commands

Build local images:

```bash
docker build -f Dockerfile.api -t dessert-ad-studio-api:latest .
docker build -f Dockerfile.app -t dessert-ad-studio-app:latest .
```

Render manifests:

```bash
kubectl kustomize deploy/k8s/base
kubectl kustomize deploy/k8s/overlays/gpu
kubectl kustomize deploy/k8s/overlays/agentops
```

Apply base stack:

```bash
kubectl apply -k deploy/k8s/base
```

Apply AgentOps stack:

```bash
kubectl apply -k deploy/k8s/overlays/agentops
```

Port-forward checks after pods are ready:

```bash
kubectl -n dessert-ad-studio port-forward svc/api 8000:8000
python scripts/api_smoke.py --base-url http://127.0.0.1:8000 --skip-generate
```

Phoenix UI for AgentOps overlay:

```bash
kubectl -n dessert-ad-studio port-forward svc/phoenix 6006:6006
```

Open:

```text
http://localhost:6006
```
