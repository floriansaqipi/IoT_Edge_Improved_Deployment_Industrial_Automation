from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import CollectorConfig


class EdgeHubTelemetrySender:
    def __init__(self, output_name: str) -> None:
        self.output_name = output_name
        self._client: Any | None = None
        self._message_type: Any | None = None

    async def __aenter__(self) -> "EdgeHubTelemetrySender":
        from azure.iot.device import Message
        from azure.iot.device.aio import IoTHubModuleClient

        self._message_type = Message
        self._client = IoTHubModuleClient.create_from_edge_environment()
        await self._client.connect()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._client is not None:
            await self._client.shutdown()

    async def send(self, message: dict[str, Any]) -> None:
        if self._client is None or self._message_type is None:
            raise RuntimeError("EdgeHubTelemetrySender must be used as an async context manager.")

        edge_message = self._message_type(_json_payload(message))
        edge_message.content_encoding = "utf-8"
        edge_message.content_type = "application/json"
        await self._client.send_message_to_output(edge_message, self.output_name)


class StdoutTelemetrySender:
    async def __aenter__(self) -> "StdoutTelemetrySender":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def send(self, message: dict[str, Any]) -> None:
        print(_json_payload(message), flush=True)


class JsonlTelemetrySender:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self._file: Any | None = None

    async def __aenter__(self) -> "JsonlTelemetrySender":
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("w", encoding="utf-8")
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._file is not None:
            self._file.close()

    async def send(self, message: dict[str, Any]) -> None:
        if self._file is None:
            raise RuntimeError("JsonlTelemetrySender must be used as an async context manager.")
        self._file.write(_json_payload(message) + "\n")
        self._file.flush()


def build_sender(config: CollectorConfig) -> EdgeHubTelemetrySender | StdoutTelemetrySender | JsonlTelemetrySender:
    if config.output_mode == "stdout":
        return StdoutTelemetrySender()
    if config.output_mode == "jsonl":
        if config.local_output_path is None:
            raise ValueError("local_output_path is required for jsonl output mode.")
        return JsonlTelemetrySender(config.local_output_path)
    return EdgeHubTelemetrySender(config.output_name)


def _json_payload(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"), sort_keys=True)
