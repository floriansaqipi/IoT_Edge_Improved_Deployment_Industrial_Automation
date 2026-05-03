from __future__ import annotations

import logging

import azure.functions as func

from cloud_processor.processor import process_event_body
from cloud_processor.tables import CloudTableWriter


_writer: CloudTableWriter | None = None


def main(event: func.EventHubEvent) -> None:
    global _writer
    if _writer is None:
        _writer = CloudTableWriter.from_env()

    metadata = dict(event.metadata or {})
    result = process_event_body(event.get_body(), metadata)
    for write in result.writes:
        _writer.write(write)

    logging.info(
        "Processed IoT Hub event as %s; valid=%s; writes=%d",
        result.message_type,
        result.valid,
        len(result.writes),
    )
