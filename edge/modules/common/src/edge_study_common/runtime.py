from __future__ import annotations

import asyncio
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from .messages import OutputMessage, decode_message_data, json_payload


Processor = Callable[[dict[str, Any]], list[OutputMessage] | Awaitable[list[OutputMessage]]]


def configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def run_iotedge_module(input_name: str, processor: Processor) -> None:
    from azure.iot.device import Message
    from azure.iot.device.aio import IoTHubModuleClient

    configure_logging()
    logger = logging.getLogger(__name__)
    client = IoTHubModuleClient.create_from_edge_environment()
    await client.connect()
    logger.info("Module connected; listening on input %s", input_name)

    try:
        while True:
            incoming = await client.receive_message_on_input(input_name)
            try:
                record = decode_message_data(incoming)
                outputs = processor(record)
                if inspect.isawaitable(outputs):
                    outputs = await outputs
                for output in outputs:
                    message = Message(json_payload(output.payload))
                    message.content_encoding = "utf-8"
                    message.content_type = "application/json"
                    await client.send_message_to_output(message, output.output_name)
            except Exception:
                logger.exception("Failed to process incoming message on %s", input_name)
    finally:
        await client.shutdown()


def run_main(input_name: str, processor: Processor) -> int:
    try:
        asyncio.run(run_iotedge_module(input_name, processor))
    except KeyboardInterrupt:
        return 130
    return 0
