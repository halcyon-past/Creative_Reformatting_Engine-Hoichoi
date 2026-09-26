"""Job-queue port. Local uses an in-process thread pool; AWS uses SQS."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

JobHandler = Callable[[dict[str, Any]], None]


class JobQueue(ABC):
    @abstractmethod
    def enqueue(self, message: dict[str, Any]) -> None: ...

    @abstractmethod
    def start(self, handler: JobHandler) -> None:
        """Begin consuming. Non-blocking."""

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def drain(self, timeout: float = 300.0) -> bool:
        """Block until the queue is empty. Returns False on timeout.

        Used by tests and the CLI; a no-op for distributed backends.
        """
