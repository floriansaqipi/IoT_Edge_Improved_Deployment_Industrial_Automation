from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from edge_study_common.cloud_output_policy import CloudOutputLimiter
from edge_study_common.messages import copy_record, json_payload, utc_now

from .config import S0PublisherConfig


logger = logging.getLogger(__name__)


class IoTHubDirectTelemetrySender:
    def __init__(self, config: S0PublisherConfig) -> None:
        self.config = config
        self.limiter = CloudOutputLimiter(
            policy=config.cloud_output_policy,
            sample_every=config.sample_every,
            max_messages_per_second=config.cloud_max_messages_per_second,
        )
        self._client: Any | None = None
        self._message_type: Any | None = None
        self._queue: asyncio.Queue[dict[str, Any]] | None = None
        self._workers: list[asyncio.Task[None]] = []
        self._started_at = time.monotonic()
        self.sent_count = 0
        self.dropped_by_policy_count = 0
        self.failed_send_count = 0

    async def __aenter__(self) -> "IoTHubDirectTelemetrySender":
        from azure.iot.device import Message
        from azure.iot.device.aio import IoTHubDeviceClient

        self._message_type = Message
        self._client = IoTHubDeviceClient.create_from_connection_string(
            self.config.iothub_device_connection_string
        )
        await self._client.connect()
        self._queue = asyncio.Queue(maxsize=self.config.send_queue_maxsize)
        self._workers = [
            asyncio.create_task(self._send_worker(), name=f"s0-iothub-sender-{index}")
            for index in range(self.config.send_worker_count)
        ]
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._queue is not None:
            try:
                await asyncio.wait_for(self._queue.join(), timeout=30)
            except TimeoutError:
                logger.warning("Timed out waiting for S0 sender queue to drain.")
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        if self._client is not None:
            await self._client.shutdown()

    async def send(self, message: dict[str, Any]) -> None:
        if self._client is None or self._message_type is None or self._queue is None:
            raise RuntimeError("IoTHubDirectTelemetrySender must be used as an async context manager.")

        elapsed = time.monotonic() - self._started_at
        limiter_record = copy_record(message)
        limiter_record["groundTruth"] = {"isAnomaly": False, "anomalyType": None}
        if not self.limiter.should_forward(limiter_record, elapsed):
            self.dropped_by_policy_count += 1
            return

        outgoing = self.prepare_message(message)
        await self._queue.put(outgoing)

    async def _send_worker(self) -> None:
        if self._queue is None or self._client is None or self._message_type is None:
            raise RuntimeError("IoTHubDirectTelemetrySender is not initialized.")
        while True:
            outgoing = await self._queue.get()
            try:
                iot_message = self._message_type(json_payload(outgoing))
                iot_message.content_encoding = "utf-8"
                iot_message.content_type = "application/json"
                iot_message.custom_properties["scenario"] = str(outgoing.get("scenario", "S0_CLOUD_ONLY"))
                iot_message.custom_properties["runId"] = str(outgoing.get("runId", ""))
                await self._client.send_message(iot_message)
                self.sent_count += 1
            except Exception:
                self.failed_send_count += 1
                logger.exception("Failed to send S0 telemetry message.")
            finally:
                self._queue.task_done()

    def prepare_message(self, message: dict[str, Any]) -> dict[str, Any]:
        outgoing = copy_record(message)
        if self.config.experiment_id_override is not None:
            outgoing["experimentId"] = self.config.experiment_id_override
        if self.config.scenario_override is not None:
            outgoing["scenario"] = self.config.scenario_override
        if self.config.run_id_override is not None:
            outgoing["runId"] = self.config.run_id_override

        now = utc_now()
        outgoing["edgeReceivedTimestamp"] = None
        outgoing["directPublisherReceivedTimestamp"] = now
        outgoing["cloudPublishTimestamp"] = utc_now()
        outgoing.setdefault("normalizedTimestamp", None)
        outgoing.setdefault("filteredTimestamp", None)
        outgoing.setdefault("anomalyTimestamp", None)
        outgoing.setdefault("cloudReceivedTimestamp", None)
        return outgoing
