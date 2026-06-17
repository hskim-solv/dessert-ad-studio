# Kubernetes Deployment

Minimal Kubernetes manifests for proving that Dessert Ad Studio can be deployed as a service stack:

- FastAPI API with `/livez` and `/readyz` probes plus `/metrics`
- Streamlit UI
- Triton Inference Server with a model repository PVC
- shared output/log PVC
- ConfigMap-driven runtime settings
- resource requests/limits and API HPA
- optional GPU overlay for Triton
- optional AgentOps overlay with OpenTelemetry Collector and Phoenix
- NGINX Ingress routing for API and UI hosts

## Build Images

```bash
docker build -f Dockerfile.api -t dessert-ad-studio-api:latest .
docker build -f Dockerfile.app -t dessert-ad-studio-app:latest .
```

Push the images to your registry and update the image names in:

- `base/api-deployment.yaml`
- `base/app-deployment.yaml`

## Prepare Triton Models

The base manifest expects a PVC named `triton-models` mounted at `/models`.
Populate it with the repository layout from `models/`, for example:

```text
/models/template_scorer/config.pbtxt
/models/template_scorer/1/model.onnx
```

For production, prefer building a small custom Triton image or using a controlled model-sync job.

## Storage Notes

The `outputs` PVC uses `ReadWriteMany` because the API can be scaled by HPA while
the Streamlit UI reads generated artifacts. Use a storage class that supports
RWX access, or replace this PVC with object storage in a production cluster.

The `triton-models` PVC is `ReadWriteOnce` because the base manifest runs one
Triton replica.

## Apply

```bash
kubectl apply -k deploy/k8s/base
```

For a GPU node pool with the NVIDIA device plugin installed:

```bash
kubectl apply -k deploy/k8s/overlays/gpu
```

For the AgentOps path:

```bash
kubectl apply -k deploy/k8s/overlays/agentops
```

This overlay sends API workflow traces to an in-cluster OpenTelemetry Collector
at `http://otel-collector:4318/v1/traces`. The collector adds Kubernetes
metadata and exports traces to Phoenix at `http://phoenix:6006/v1/traces`.

Phoenix stores trace data in pod-local `emptyDir` storage at `/phoenix_data`, so
the AgentOps overlay is ephemeral and intended for local/demo evidence. Do not
use it for real customer inputs without reviewing trace attributes, retention,
and redaction policy.

## Check

Render locally without a cluster:

```bash
kubectl kustomize deploy/k8s/base
kubectl kustomize deploy/k8s/overlays/gpu
kubectl kustomize deploy/k8s/overlays/agentops
```

Check a running base stack:

```bash
kubectl -n dessert-ad-studio get pods
kubectl -n dessert-ad-studio port-forward svc/api 8000:8000
python scripts/api_smoke.py --base-url http://127.0.0.1:8000 --skip-generate
```

The smoke uses `--skip-generate` here because the Triton model PVC must be populated before full generation is expected to pass.

Fail-closed local/test context smoke:

```bash
.venv/bin/python scripts/k8s_live_smoke.py \
  --context kind-dessert-ad-studio \
  --kustomize-path deploy/k8s/base \
  --namespace dessert-ad-studio
```

The script refuses unknown Kubernetes contexts unless `--allow-unsafe-context`
is passed intentionally.

For AgentOps UI evidence:

```bash
kubectl -n dessert-ad-studio port-forward svc/phoenix 6006:6006
```

Open:

```text
http://localhost:6006
```

See `docs/evidence/k8s-deployment.md` for captured render evidence.
