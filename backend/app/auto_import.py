import asyncio
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text

from import_items import run

from .db import SessionLocal, engine
from .models import AutoImportConfig, ImportRunHistory


logger = logging.getLogger(__name__)
IMPORT_LOCK_ID = 19000001
POLL_SECONDS = 10


class ImportAlreadyRunningError(RuntimeError):
    pass


def get_import_config(db=None) -> AutoImportConfig:
    if db is not None:
        config = db.get(AutoImportConfig, 1)
        if not config:
            raise RuntimeError("Chưa khởi tạo cấu hình import tự động")
        return config
    with SessionLocal() as session:
        config = session.get(AutoImportConfig, 1)
        if not config:
            raise RuntimeError("Chưa khởi tạo cấu hình import tự động")
        session.expunge(config)
        return config


def _set_run_started(trigger: str, source_name: str) -> int:
    with SessionLocal.begin() as db:
        config = get_import_config(db)
        config.is_running = True
        config.last_trigger = trigger
        config.last_started_at = datetime.now(timezone.utc)
        config.last_status = "RUNNING"
        config.last_error = None
        history = ImportRunHistory(
            trigger=trigger,
            source_name=source_name,
            status="RUNNING",
            started_at=config.last_started_at,
        )
        db.add(history)
        db.flush()
        return history.id


def _set_run_finished(run_id: int, result: dict | None = None, error: Exception | None = None) -> None:
    with SessionLocal.begin() as db:
        config = get_import_config(db)
        history = db.get(ImportRunHistory, run_id)
        completed_at = datetime.now(timezone.utc)
        config.is_running = False
        config.last_completed_at = completed_at
        if error:
            config.last_status = "FAILED"
            config.last_error = str(error)[:4000]
            if history:
                history.status = "FAILED"
                history.completed_at = completed_at
                history.error = str(error)[:4000]
        else:
            config.last_status = "SUCCESS"
            config.last_imported = int((result or {}).get("imported", 0))
            config.last_skipped = int((result or {}).get("skipped", 0))
            config.last_error = None
            if history:
                history.status = "SUCCESS"
                history.completed_at = completed_at
                history.imported = config.last_imported
                history.skipped = config.last_skipped


def import_is_running() -> bool:
    """Read the PostgreSQL lock instead of trusting a possibly stale DB flag."""
    with engine.connect() as connection:
        locked = connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": IMPORT_LOCK_ID},
        )
        if locked:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": IMPORT_LOCK_ID},
            )
            return False
        return True


def recover_interrupted_import() -> bool:
    """Mark a stale RUNNING flag left behind by a terminated process."""
    with engine.connect() as connection:
        locked = connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": IMPORT_LOCK_ID},
        )
        if not locked:
            return False
        try:
            with SessionLocal.begin() as db:
                config = get_import_config(db)
                if not config.is_running:
                    return False
                config.is_running = False
                config.last_status = "FAILED"
                config.last_completed_at = datetime.now(timezone.utc)
                config.last_error = (
                    "Lần import trước bị gián đoạn khi dịch vụ dừng; "
                    "giao dịch cơ sở dữ liệu đã được hoàn tác."
                )
                interrupted = db.query(ImportRunHistory).filter(
                    ImportRunHistory.status == "RUNNING"
                ).all()
                for history in interrupted:
                    history.status = "FAILED"
                    history.completed_at = config.last_completed_at
                    history.error = config.last_error
                return True
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": IMPORT_LOCK_ID},
            )


def execute_import(source_path: str, trigger: str, source_name: str | None = None) -> dict:
    source = Path(source_path)
    with engine.connect() as connection:
        locked = connection.scalar(text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": IMPORT_LOCK_ID})
        if not locked:
            raise ImportAlreadyRunningError("Một tác vụ import khác đang chạy")
        run_id = None
        try:
            run_id = _set_run_started(trigger, source_name or source.name)
            if not source.is_file():
                raise FileNotFoundError(f"Không tìm thấy file: {source}")
            if source.suffix.lower() not in {".xlsx", ".csv"}:
                raise ValueError("File import phải có định dạng .xlsx hoặc .csv")
            with tempfile.TemporaryDirectory(prefix="masterdata-import-") as temp_dir:
                snapshot = Path(temp_dir) / source.name
                shutil.copy2(source, snapshot)
                result = run(str(snapshot), initialize_schema=False)
            _set_run_finished(run_id, result=result)
            logger.info("Import %s hoàn tất từ %s: %s", trigger, source, result)
            return result
        except Exception as exc:
            if run_id is not None:
                _set_run_finished(run_id, error=exc)
            logger.exception("Import %s thất bại từ file %s", trigger, source)
            raise
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": IMPORT_LOCK_ID})


def import_configured_file() -> dict:
    config = get_import_config()
    return execute_import(config.file_path, "AUTO")


def _local_now(config: AutoImportConfig) -> datetime:
    try:
        zone = ZoneInfo(config.timezone)
    except ZoneInfoNotFoundError:
        logger.error("Múi giờ auto import không hợp lệ: %s", config.timezone)
        zone = ZoneInfo("UTC")
    return datetime.now(zone)


async def auto_import_worker() -> None:
    logger.info("Job theo dõi cấu hình import tự động đã khởi động")
    last_run_key = None
    while True:
        try:
            config = get_import_config()
            now = _local_now(config)
            run_key = (now.date().isoformat(), config.hour, config.minute)
            due = config.enabled and now.hour == config.hour and now.minute == config.minute
            if due and run_key != last_run_key:
                last_run_key = run_key
                try:
                    await asyncio.to_thread(import_configured_file)
                except ImportAlreadyRunningError:
                    logger.info("Bỏ qua auto import vì một tác vụ khác đang chạy")
                except Exception:
                    logger.exception("Auto import thất bại; job vẫn tiếp tục theo dõi lịch")
        except Exception:
            logger.exception("Không thể đọc cấu hình auto import")
        await asyncio.sleep(POLL_SECONDS)
