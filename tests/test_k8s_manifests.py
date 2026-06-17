from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ASYNC_OVERLAY = Path("deploy/k8s/overlays/async")


def test_k8s_async_overlay_declares_worker_redis_and_postgres() -> None:
    kustomization = (ASYNC_OVERLAY / "kustomization.yaml").read_text(encoding="utf-8")
    assert "../../base" in kustomization
    assert "postgres-auth.yaml" in kustomization
    assert "pgvector.yaml" in kustomization
    assert "redis.yaml" in kustomization
    assert "worker-deployment.yaml" in kustomization
    assert "api-async-patch.yaml" in kustomization
    assert "init/002_generation_jobs.sql" in kustomization

    overlay_text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(ASYNC_OVERLAY.glob("*.yaml"))
    )
    for needle in [
        "name: worker",
        "scripts/run_generation_worker.py",
        "name: redis",
        "redis-server",
        "name: pgvector",
        "pgvector/pgvector:pg16",
        "GENERATION_QUEUE_BACKEND: rq",
        "GENERATION_HISTORY_BACKEND: postgres",
        "GENERATION_HISTORY_DSN",
        "redis://redis:6379/0",
    ]:
        assert needle in overlay_text


@pytest.mark.skipif(shutil.which("kubectl") is None, reason="kubectl is not installed")
def test_k8s_async_overlay_renders_with_kubectl_kustomize() -> None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(ASYNC_OVERLAY)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    rendered = result.stdout
    for needle in [
        "kind: Deployment\nmetadata:\n  name: worker",
        "kind: Deployment\nmetadata:\n  name: redis",
        "kind: Deployment\nmetadata:\n  name: pgvector",
        "kind: Service\nmetadata:\n  name: redis",
        "kind: Service\nmetadata:\n  name: pgvector",
        "kind: PersistentVolumeClaim\nmetadata:\n  name: pgvector-data",
        "name: pgvector-init-sql",
        "GENERATION_QUEUE_BACKEND: rq",
        "GENERATION_HISTORY_BACKEND: postgres",
    ]:
        assert needle in rendered
    assert rendered.count("namespace: dessert-ad-studio") >= 10
