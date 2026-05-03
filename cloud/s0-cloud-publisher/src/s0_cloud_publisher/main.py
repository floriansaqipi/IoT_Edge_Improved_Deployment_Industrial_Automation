from __future__ import annotations

import asyncio
import logging

from opcua_collector.collector import collect_forever

from .config import S0PublisherConfig
from .iothub_sender import IoTHubDirectTelemetrySender


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


async def run() -> None:
    config = S0PublisherConfig.from_env()
    configure_logging(config.log_level)
    logging.getLogger(__name__).info("Starting S0 direct cloud publisher for %s", config.opcua_endpoint)
    async with IoTHubDirectTelemetrySender(config) as sender:
        await collect_forever(config.to_collector_config(), sender)


def main() -> int:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
