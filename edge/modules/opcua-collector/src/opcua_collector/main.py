from __future__ import annotations

import asyncio
import logging

from .collector import collect_forever
from .config import CollectorConfig
from .edge_output import build_sender


async def _run() -> None:
    config = CollectorConfig.from_env()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    async with build_sender(config) as sender:
        await collect_forever(config, sender)


def main() -> int:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
