import asyncio
import logging
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from import_items import run

from .config import get_settings
from .db import engine


logger = logging.getLogger(__name__)
settings = get_settings()
IMPORT_LOCK_ID = 19000001


def _timezone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.auto_import_timezone)
    except ZoneInfoNotFoundError:
        logger.error("Múi giờ auto import không hợp lệ: %s", settings.auto_import_timezone)
        return ZoneInfo("UTC")


def seconds_until_next_import(now: datetime | None = None) -> float:
    timezone = _timezone()
    current = now.astimezone(timezone) if now else datetime.now(timezone)
    target = current.replace(
        hour=settings.auto_import_hour,
        minute=settings.auto_import_minute,
        second=0,
        microsecond=0,
    )
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()


def import_configured_file() -> None:
    source = Path(settings.auto_import_file_path)
    if not source.is_file():
        logger.error("Không tìm thấy file auto import: %s", source)
        return
    if source.suffix.lower() not in {".xlsx", ".csv"}:
        logger.error("File auto import phải có định dạng .xlsx hoặc .csv: %s", source)
        return

    with engine.connect() as connection:
        locked = connection.scalar(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": IMPORT_LOCK_ID})
        if not locked:
            logger.info("Bỏ qua auto import vì một instance khác đang thực hiện")
            return
        try:
            with tempfile.TemporaryDirectory(prefix="masterdata-import-") as temp_dir:
                snapshot = Path(temp_dir) / source.name
                shutil.copy2(source, snapshot)
                result = run(str(snapshot))
            logger.info(
                "Auto import hoàn tất từ %s: %s dòng, bỏ qua %s dòng",
                source,
                result["imported"],
                result["skipped"],
            )
        except Exception:
            logger.exception("Auto import thất bại từ file %s", source)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": IMPORT_LOCK_ID})


async def auto_import_worker() -> None:
    if not settings.auto_import_enabled:
        logger.info("Auto import danh mục đang tắt")
        return
    if not 0 <= settings.auto_import_hour <= 23 or not 0 <= settings.auto_import_minute <= 59:
        logger.error("Giờ auto import không hợp lệ: %s:%s", settings.auto_import_hour, settings.auto_import_minute)
        return

    logger.info(
        "Đã lập lịch auto import %02d:%02d mỗi ngày (%s), file %s",
        settings.auto_import_hour,
        settings.auto_import_minute,
        settings.auto_import_timezone,
        settings.auto_import_file_path,
    )
    while True:
        await asyncio.sleep(seconds_until_next_import())
        try:
            await asyncio.to_thread(import_configured_file)
        except Exception:
            logger.exception("Không thể khởi chạy auto import; lịch ngày tiếp theo vẫn được giữ")
