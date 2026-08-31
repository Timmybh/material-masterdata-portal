import asyncio
import json
import logging
import logging.config
from pathlib import Path

from .auto_import import auto_import_worker, import_job_worker, recover_interrupted_import
from .request_expiry import request_expiry_worker


def configure_logging() -> None:
    config_path = Path(__file__).resolve().parents[1] / "logging.json"
    if config_path.is_file():
        with config_path.open(encoding="utf-8") as source:
            logging.config.dictConfig(json.load(source))


async def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)
    if recover_interrupted_import():
        logger.warning("Recovered an interrupted item import state")
    logger.info("Background jobs started")
    await asyncio.gather(
        request_expiry_worker(),
        auto_import_worker(),
        import_job_worker(),
    )


if __name__ == "__main__":
    asyncio.run(main())
