from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import azure.functions as func

from cloud_processor.processor import INVALID_TABLE, TableWrite, process_event_body
from cloud_processor.tables import CloudTableWriter


app = func.FunctionApp()
_writer: CloudTableWriter | None = None


@app.function_name(name="ProcessIoTHubTelemetry")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="%IOTHUB_EVENTHUB_NAME%",
    connection="IOTHUB_EVENTHUB_CONNECTION",
    consumer_group="%IOTHUB_CONSUMER_GROUP%",
)
def process_iot_hub_telemetry(event: func.EventHubEvent) -> None:
    global _writer
    if _writer is None:
        _writer = CloudTableWriter.from_env()

    for item in _as_events(event):
        body, metadata = _event_body_and_metadata(item)
        try:
            result = process_event_body(body, metadata)
            for write in result.writes:
                _writer.write(write)
        except Exception as exc:
            logging.exception("Failed to process IoT Hub event.")
            _writer.write(_function_error_write(exc, body))
            raise

        logging.info(
            "Processed IoT Hub event as %s; valid=%s; writes=%d",
            result.message_type,
            result.valid,
            len(result.writes),
        )


def _as_events(event: Any) -> list[Any]:
    if isinstance(event, list):
        return event
    return [event]


def _event_body_and_metadata(event: Any) -> tuple[bytes, dict[str, Any]]:
    if hasattr(event, "get_body"):
        metadata = dict(getattr(event, "metadata", None) or {})
        return event.get_body(), metadata
    if isinstance(event, bytes):
        return event, {}
    if isinstance(event, str):
        return event.encode("utf-8"), {}
    return json.dumps(event, default=str, separators=(",", ":")).encode("utf-8"), {}


def _function_error_write(exc: Exception, body: bytes) -> TableWrite:
    return TableWrite(
        INVALID_TABLE,
        {
            "PartitionKey": "function-error",
            "RowKey": uuid.uuid4().hex,
            "messageType": "function-error",
            "error": repr(exc),
            "payloadJson": body.decode("utf-8", errors="replace")[:32000],
        },
    )
