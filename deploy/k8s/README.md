# Kubernetes Deployment

Minimal Kubernetes manifests for proving that Dessert Ad Studio can be deployed as a service stack:

- FastAPI API with `/livez`, `/readyz`, and `/metrics` probes
- Streamlit UI
- Triton Inference Server with a model repository PVC
- shared output/log PVC
- ConfigMap-driven runtime settings
- optional GPU overlay for Triton
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

## Apply

```bash
kubectl apply -k deploy/k8s/base
```

For a GPU node pool with the NVIDIA device plugin installed:

```bash
kubectl apply -k deploy/k8s/overlays/gpu
```

## Check

```bash
kubectl -n dessert-ad-studio get pods
kubectl -n dessert-ad-studio port-forward svc/api 8000:8000
python scripts/api_smoke.py --base-url http://127.0.0.1:8000 --skip-generate
```

The smoke uses `--skip-generate` here because the Triton model PVC must be populated before full generation is expected to pass.
