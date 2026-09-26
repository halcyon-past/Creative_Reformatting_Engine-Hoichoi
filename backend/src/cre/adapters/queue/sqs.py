"""SQS-backed queue for the AWS deployment.

The consumer side runs in the worker container (ECS/Fargate); the API container
only ever calls :meth:`enqueue`.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from cre.logging_config import get_logger
from cre.ports.queue import JobHandler, JobQueue

log = get_logger(__name__)


class SQSQueue(JobQueue):
    def __init__(
        self,
        queue_url: str,
        region: str | None = None,
        client: Any | None = None,
        concurrency: int = 2,
        visibility_timeout: int = 900,
        wait_time: int = 20,
    ) -> None:
        if client is None:
            import boto3

            client = boto3.client("sqs", region_name=region)
        self.client = client
        self.queue_url = queue_url
        self.concurrency = max(1, concurrency)
        self.visibility_timeout = visibility_timeout
        self.wait_time = wait_time
        self._threads: list[threading.Thread] = []
        self._running = False
        self._handler: JobHandler | None = None

    def enqueue(self, message: dict[str, Any]) -> None:
        self.client.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps(message))

    def start(self, handler: JobHandler) -> None:
        if self._running:
            return
        self._handler = handler
        self._running = True
        for i in range(self.concurrency):
            t = threading.Thread(target=self._loop, name=f"cre-sqs-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        log.info("queue.started", backend="sqs", concurrency=self.concurrency)

    def _loop(self) -> None:
        while self._running:
            try:
                resp = self.client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=self.wait_time,
                    VisibilityTimeout=self.visibility_timeout,
                )
            except Exception:  # pragma: no cover - network
                log.exception("queue.receive_failed")
                continue
            for msg in resp.get("Messages", []):
                try:
                    assert self._handler is not None
                    self._handler(json.loads(msg["Body"]))
                except Exception:
                    log.exception("queue.handler_failed", message_id=msg.get("MessageId"))
                    continue  # leave it for redrive/DLQ
                self.client.delete_message(
                    QueueUrl=self.queue_url, ReceiptHandle=msg["ReceiptHandle"]
                )

    def stop(self) -> None:
        self._running = False
        for t in self._threads:
            t.join(timeout=self.wait_time + 5)
        self._threads.clear()

    def drain(self, timeout: float = 300.0) -> bool:
        # Not meaningful for a distributed queue; callers poll job status instead.
        return True
