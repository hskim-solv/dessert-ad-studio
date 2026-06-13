# Kubernetes Deployment Evidence

Date: 2026-06-13

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
- Shared output/log PVC configured as `ReadWriteMany` so API HPA does not rely
  on a single-node `ReadWriteOnce` mount.
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
rwx_outputs=True
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
assert outputs["spec"]["accessModes"] == ["ReadWriteMany"]
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

## What This Proves

- The API, UI, Triton, Ingress, HPA, and AgentOps manifests render through
  Kubernetes-native Kustomize.
- API readiness is tied to `/readyz`; liveness is tied to `/livez`.
- Streamlit and Triton have service-specific probes instead of generic TCP-only
  checks.
- API autoscaling has CPU resource requests, which are required for CPU
  utilization based HPA behavior.
- The AgentOps overlay uses an in-cluster collector boundary instead of having
  application pods export directly to Phoenix.

## What This Does Not Prove Yet

- No live cluster pod scheduling screenshot is included in this evidence file.
- `kubectl apply --dry-run=client` still attempted API discovery against the
  current kube context (`localhost:8080`) and failed because no local cluster is
  running. This evidence therefore uses `kubectl kustomize` render checks plus
  local YAML structural checks.
- The Triton model PVC still needs to be populated in a real cluster before full
  `/generate` traffic should be expected to pass.
- The shared outputs PVC requires a storage class that supports `ReadWriteMany`,
  or a production replacement such as object storage.
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
