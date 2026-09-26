"""In-process queue backed by a thread pool.

Media work is CPU/IO heavy and releases the GIL inside OpenCV and ffmpeg, so a
thread pool keeps the API responsive without a broker. Same semantics as the
SQS adapter from the caller's point of view.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any

from cre.logging_config import get_logger
from cre.ports.queue import JobHandler, JobQueue

log = get_logger(__name__)

_SHUTDOWN = object()


class InMemoryQueue(JobQueue):
    def __init__(self, concurrency: int = 2) -> None:
        self.concurrency = max(1, concurrency)
        self._q: queue.Queue[Any] = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._handler: JobHandler | None = None
        self._running = False
        self._inflight = 0
        self._lock = threading.Lock()

    def enqueue(self, message: dict[str, Any]) -> None:
        self._q.put(message)

    def start(self, handler: JobHandler) -> None:
        if self._running:
            return
        self._handler = handler
        self._running = True
        for i in range(self.concurrency):
            t = threading.Thread(target=self._loop, name=f"cre-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        log.info("queue.started", backend="inmemory", concurrency=self.concurrency)

    def _loop(self) -> None:
        while self._running:
            try:
                message = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if message is _SHUTDOWN:
                self._q.task_done()
                break
            with self._lock:
                self._inflight += 1
            try:
                assert self._handler is not None
                self._handler(message)
            except Exception:
                log.exception("queue.handler_failed", message=message)
            finally:
                with self._lock:
                    self._inflight -= 1
                self._q.task_done()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for _ in self._threads:
            self._q.put(_SHUTDOWN)
        for t in self._threads:
            t.join(timeout=5.0)
        self._threads.clear()
        log.info("queue.stopped", backend="inmemory")

    def drain(self, timeout: float = 300.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                idle = self._q.unfinished_tasks == 0 and self._inflight == 0
            if idle:
                return True
            time.sleep(0.1)
        return False
