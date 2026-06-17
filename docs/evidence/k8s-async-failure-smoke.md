# Kubernetes Async Failure-Injection Smoke Evidence

Date: 2026-06-17

## Scope

This evidence covers a local `kind` failure-injection check for the Kubernetes
async overlay. It does not claim automatic retry, cancellation, dead-letter
queues, or multi-worker production resilience. It proves the current Redis/RQ
status path survives a worker outage window: a generation job remains queued
while `deploy/worker` has zero replicas, and the same job succeeds after the
worker is restored.

## Command

```bash
.venv/bin/python scripts/k8s_async_failure_smoke.py \
  --context kind-dessert-ad-studio \
  --namespace dessert-ad-studio \
  --local-port 18082 \
  --timeout 240 \
  --pending-observation-count 3 \
  --poll-interval 2 \
  --summary docs/evidence/k8s-async-failure-smoke-summary.json
```

Result:

```text
k8s_async_failure_smoke=passed
worker_scaled_down=True
job_pending_without_worker=True
worker_restored=True
job_succeeded_after_restore=True
```

The machine-readable summary is stored at
[`k8s-async-failure-smoke-summary.json`](k8s-async-failure-smoke-summary.json).

## What This Proves

- The script refuses non-local Kubernetes contexts unless explicitly overridden.
- `deploy/worker` can be scaled to zero and restored to one replica.
- While the worker is down, a submitted generation job stays queued for 3
  observations.
- After the worker is restored, the same job reaches `succeeded`.
- The evidence stores only a job id hash and status transitions, not raw product
  names, user constraints, prompts, model responses, or raw job ids.

## Recovery Check

After the smoke:

```bash
kubectl --context kind-dessert-ad-studio \
  -n dessert-ad-studio \
  get deploy worker \
  -o jsonpath='{.status.readyReplicas}/{.spec.replicas}{"\n"}'
```

Result:

```text
1/1
```

No `kubectl port-forward` process remained for `18082:8000`.

## Remaining Gap

Automatic retry, worker timeout, cancellation, and dead-letter handling are
explicit non-support in the current API policy. Multi-worker failure handling
remains unclaimed until it has explicit behavior and tests.
