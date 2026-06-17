from __future__ import annotations

import os
from pathlib import Path
import sys
from time import monotonic, sleep

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, Worker


def _ensure_repo_root_on_path() -> None:
    repo_root = str(Path(__file__).resolve().parents[1])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _wait_for_redis(redis: Redis, timeout_seconds: float, interval_seconds: float = 0.5) -> None:
    deadline = monotonic() + timeout_seconds
    last_error: Exception | None = None
    while monotonic() < deadline:
        try:
            redis.ping()
            return
        except RedisError as exc:
            last_error = exc
            sleep(interval_seconds)
    raise RuntimeError(f"Redis did not become ready within {timeout_seconds:.1f}s: {last_error}")


def main() -> None:
    _ensure_repo_root_on_path()
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    _wait_for_redis(
        redis,
        timeout_seconds=float(os.getenv("GENERATION_WORKER_REDIS_READY_TIMEOUT_SECONDS", "60")),
    )
    queue_name = os.getenv("GENERATION_QUEUE_NAME", "ad-generation")
    queue = Queue(queue_name, connection=redis)
    worker_name = os.getenv("GENERATION_WORKER_NAME")
    kwargs = {"name": worker_name} if worker_name else {}
    worker = Worker([queue], connection=redis, log_job_description=False, **kwargs)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
