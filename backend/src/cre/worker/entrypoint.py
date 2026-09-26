"""Standalone worker process.

Runs the same :class:`Worker` the API hosts in-process locally, but with no web
server attached. This is what the ECS worker service executes, so rendering
scales independently of API traffic.

Locally you rarely need it -- the API runs a worker in-process -- but it is
useful for reproducing the deployed topology:

    python -m cre.worker.entrypoint
"""

from __future__ import annotations

import asyncio
import signal
import sys
import threading

from cre.config import get_settings
from cre.container import build_container
from cre.logging_config import configure_logging, get_logger

log = get_logger(__name__)


def main() -> int:
    settings = get_settings()
    configure_logging(settings.env, settings.debug)

    if settings.worker_concurrency < 1:
        log.error("worker.no_concurrency", configured=settings.worker_concurrency)
        return 2

    container = build_container(settings)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(container.startup(start_worker=True))

    log.info(
        "worker.running",
        queue=settings.queue_backend.value,
        storage=settings.storage_backend.value,
        concurrency=settings.worker_concurrency,
    )

    stop = threading.Event()

    def shutdown(signum: int, _frame: object) -> None:
        log.info("worker.signal", signal=signum)
        stop.set()

    # SIGTERM is what ECS sends when draining a task; handle it so an in-flight
    # render is not killed mid-write and left as a partial object.
    for name in ("SIGTERM", "SIGINT"):
        sig = getattr(signal, name, None)
        if sig is not None:
            signal.signal(sig, shutdown)

    try:
        stop.wait()
    finally:
        log.info("worker.stopping")
        loop.run_until_complete(container.shutdown())
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
