# Kubernetes Deployment Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Kubernetes manifests into a stronger deployment evidence pack with probes, resources, autoscaling, OTEL Collector routing, and reproducible validation notes.

**Architecture:** Keep the existing FastAPI + Streamlit + Triton base deployment. Add narrowly scoped production readiness resources and an AgentOps overlay that routes workflow traces through an in-cluster OpenTelemetry Collector to Phoenix. Evidence is generated through local manifest rendering and focused smoke tests rather than requiring a live cloud cluster.

**Tech Stack:** Kubernetes `apps/v1`, `networking.k8s.io/v1`, `autoscaling/v2`, Kustomize via `kubectl kustomize`, OpenTelemetry Collector Contrib, NGINX Ingress, FastAPI probes, Triton health endpoints.

---

### Task 1: Strengthen Base K8s Manifests

**Files:**
- Modify: `deploy/k8s/base/api-deployment.yaml`
- Modify: `deploy/k8s/base/app-deployment.yaml`
- Modify: `deploy/k8s/base/triton-deployment.yaml`
- Create: `deploy/k8s/base/api-hpa.yaml`
- Modify: `deploy/k8s/base/kustomization.yaml`

- [x] Add `startupProbe`, resource requests/limits, and graceful termination fields to API, app, and Triton deployments.
- [x] Add an `autoscaling/v2` HorizontalPodAutoscaler for the API deployment.
- [x] Add `api-hpa.yaml` to base kustomization.
- [x] Verify with `kubectl kustomize deploy/k8s/base`.

### Task 2: Add AgentOps OTEL Collector Overlay

**Files:**
- Create: `deploy/k8s/overlays/agentops/kustomization.yaml`
- Create: `deploy/k8s/overlays/agentops/api-otel-patch.yaml`
- Create: `deploy/k8s/overlays/agentops/otel-collector.yaml`
- Create: `deploy/k8s/overlays/agentops/phoenix.yaml`

- [x] Add a Phoenix deployment/service for local AgentOps proof.
- [x] Add an OpenTelemetry Collector deployment/service with OTLP HTTP/GRPC receivers, `k8sattributes`, batching, and OTLP HTTP export to Phoenix.
- [x] Patch API environment variables to export workflow traces to the collector.
- [x] Verify with `kubectl kustomize deploy/k8s/overlays/agentops`.

### Task 3: Document Architecture Decision and Evidence

**Files:**
- Create: `docs/adr/0005-kubernetes-deployment-evidence.md`
- Create: `docs/evidence/k8s-deployment.md`
- Modify: `deploy/k8s/README.md`
- Modify: `README.md`

- [x] Record the K8s evidence decision with criteria and alternatives.
- [x] Record local validation commands and outputs.
- [x] Update deployment README with base, GPU, and AgentOps overlay usage.
- [x] Add a short root README pointer to the deployment evidence.

### Task 4: Verification and Commit

**Files:**
- All files changed by Tasks 1-3.

- [x] Run `kubectl kustomize deploy/k8s/base >/tmp/dessert-k8s-base.yaml`.
- [x] Run `kubectl kustomize deploy/k8s/overlays/gpu >/tmp/dessert-k8s-gpu.yaml`.
- [x] Run `kubectl kustomize deploy/k8s/overlays/agentops >/tmp/dessert-k8s-agentops.yaml`.
- [x] Run `python - <<'PY' ...` YAML sanity checks against the rendered manifests.
- [x] Run focused tests for API health and OTEL smoke coverage.
- [x] Commit only the scoped K8s evidence files.
