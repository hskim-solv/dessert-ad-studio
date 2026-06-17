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
- optional async overlay with Redis/RQ worker and Postgres/pgvector job history
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

The base `outputs` PVC uses `ReadWriteOnce` so it works on local/test clusters
such as `kind` with the default local-path provisioner. This is enough for the
single-node deployability smoke. For multi-node production scaling, move
generated artifacts to object storage or add an overlay with a storage class
that supports `ReadWriteMany`.

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

For the async job path:

```bash
kubectl apply -k deploy/k8s/overlays/async
```

This overlay adds Redis, pgvector/Postgres, a `worker` Deployment running
`scripts/run_generation_worker.py`, and API environment wiring for
`GENERATION_QUEUE_BACKEND=rq` plus `GENERATION_HISTORY_BACKEND=postgres`.
The included `postgres-auth` Secret uses a local-demo placeholder and must be
replaced before non-local use.

## Check

Render locally without a cluster:

```bash
kubectl kustomize deploy/k8s/base
kubectl kustomize deploy/k8s/overlays/gpu
kubectl kustomize deploy/k8s/overlays/agentops
kubectl kustomize deploy/k8s/overlays/async
```

Check a running base stack:

```bash
kubectl -n dessert-ad-studio get pods
kubectl -n dessert-ad-studio port-forward svc/api 8000:8000
python scripts/api_smoke.py --base-url http://127.0.0.1:8000
```

Check a running async stack:

```bash
kubectl -n dessert-ad-studio rollout status deploy/redis
kubectl -n dessert-ad-studio rollout status deploy/pgvector
kubectl -n dessert-ad-studio rollout status deploy/worker
kubectl -n dessert-ad-studio port-forward svc/api 8000:8000
API_BASE_URL=http://127.0.0.1:8000 python scripts/generation_job_smoke.py
```

Full generation requires the Triton model PVC to contain the repository layout
from `models/`. The fail-closed smoke below performs that sync automatically.

Fail-closed local/test context smoke:

```bash
.venv/bin/python scripts/k8s_live_smoke.py \
  --context kind-dessert-ad-studio \
  --kustomize-path deploy/k8s/base \
  --namespace dessert-ad-studio \
  --timeout 900 \
  --summary docs/evidence/k8s-live-smoke-summary.json
```

The script refuses unknown Kubernetes contexts unless `--allow-unsafe-context`
is passed intentionally. It applies the base stack, syncs `models/` into the
`triton-models` PVC, restarts Triton, waits for `api`/`app`/`triton`, runs API
smoke, and writes a redacted summary.

For AgentOps UI evidence:

```bash
kubectl -n dessert-ad-studio port-forward svc/phoenix 6006:6006
```

Open:

```text
http://localhost:6006
```

See `docs/evidence/k8s-deployment.md` for captured render and live smoke
evidence.
