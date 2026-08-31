import asyncio
import logging
import os
import shutil
import socket
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from import_items import run

from .config import get_settings
from .db import SessionLocal, engine
from .models import AutoImportConfig, ImportRunHistory


logger = logging.getLogger(__name__)
settings = get_settings()
IMPORT_LOCK_ID = 19000001
AUTO_POLL_SECONDS = 10
ACTIVE_STATUSES = ("queued", "running")


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


def get_import_spool_dir() -> Path:
    spool_dir = Path(settings.import_spool_dir).expanduser().resolve()
    spool_dir.mkdir(parents=True, exist_ok=True)
    return spool_dir


def get_import_job(db, job_id: uuid.UUID) -> ImportRunHistory | None:
    return db.scalar(select(ImportRunHistory).where(ImportRunHistory.job_id == job_id))


def _active_import_job(db) -> ImportRunHistory | None:
    return db.scalar(
        select(ImportRunHistory)
        .where(ImportRunHistory.status.in_(ACTIVE_STATUSES))
        .order_by(ImportRunHistory.queued_at)
        .limit(1)
    )


def import_is_running() -> bool:
    """Return queued/running state from PostgreSQL, shared by every process."""
    with SessionLocal() as db:
        return _active_import_job(db) is not None


def enqueue_import_job(
    source_path: str,
    trigger: str,
    source_name: str | None = None,
    *,
    job_id: uuid.UUID | None = None,
    schedule_key: str | None = None,
) -> ImportRunHistory:
    source = Path(source_path)
    if source.suffix.lower() not in {".xlsx", ".csv"}:
        raise ValueError("File import phải có định dạng .xlsx hoặc .csv")
    trigger = trigger.upper()
    if trigger not in {"MANUAL", "AUTO"}:
        raise ValueError("Nguồn kích hoạt import không hợp lệ")
    queued_at = datetime.now(timezone.utc)
    job = ImportRunHistory(
        job_id=job_id or uuid.uuid4(),
        trigger=trigger,
        source_name=source_name or source.name,
        source_path=str(source),
        schedule_key=schedule_key,
        status="queued",
        phase="queued",
        queued_at=queued_at,
        # Bản cài đặt cũ có started_at NOT NULL; worker cập nhật lại khi nhận job.
        started_at=queued_at,
    )
    try:
        with SessionLocal.begin() as db:
            db.add(job)
            db.flush()
            config = get_import_config(db)
            config.is_running = True
            config.last_trigger = trigger
            config.last_status = "QUEUED"
            config.last_error = None
    except IntegrityError as exc:
        with SessionLocal() as db:
            if schedule_key:
                existing = db.scalar(
                    select(ImportRunHistory).where(
                        ImportRunHistory.schedule_key == schedule_key
                    )
                )
                if existing:
                    db.expunge(existing)
                    return existing
            active = _active_import_job(db)
            active_id = active.job_id if active else None
        detail = f" (job {active_id})" if active_id else ""
        raise ImportAlreadyRunningError(
            f"Một tác vụ import khác đang chờ hoặc đang chạy{detail}"
        ) from exc
    logger.info(
        "Import job queued job_id=%s trigger=%s source=%s schedule_key=%s",
        job.job_id,
        job.trigger,
        job.source_name,
        schedule_key,
    )
    return job


def _claim_next_import_job(worker_id: str) -> dict | None:
    with SessionLocal.begin() as db:
        job = db.scalar(
            select(ImportRunHistory)
            .where(ImportRunHistory.status == "queued")
            .order_by(ImportRunHistory.queued_at, ImportRunHistory.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        started_at = datetime.now(timezone.utc)
        job.status = "running"
        job.phase = "validating"
        job.started_at = started_at
        job.worker_id = worker_id
        job.processed = 0
        job.total_rows = None
        config = get_import_config(db)
        config.is_running = True
        config.last_trigger = job.trigger
        config.last_started_at = started_at
        config.last_status = "RUNNING"
        config.last_error = None
        return {
            "id": job.id,
            "job_id": job.job_id,
            "trigger": job.trigger,
            "source_name": job.source_name,
            "source_path": job.source_path,
        }


def _set_job_progress(
    history_id: int, phase: str, processed: int | None, total_rows: int | None
) -> None:
    with SessionLocal.begin() as db:
        job = db.get(ImportRunHistory, history_id)
        if not job or job.status != "running":
            return
        job.phase = phase
        job.processed = processed
        job.total_rows = total_rows


def _finish_import_job(
    history_id: int,
    duration_seconds: float,
    result: dict | None = None,
    error: Exception | None = None,
) -> None:
    with SessionLocal.begin() as db:
        job = db.get(ImportRunHistory, history_id)
        if not job:
            return
        completed_at = datetime.now(timezone.utc)
        config = get_import_config(db)
        job.completed_at = completed_at
        job.duration_seconds = round(duration_seconds, 3)
        config.is_running = False
        config.last_completed_at = completed_at
        if error:
            message = str(error)[:4000]
            job.status = "failed"
            job.phase = "failed"
            job.error = message
            config.last_status = "FAILED"
            config.last_error = message
        else:
            imported = int((result or {}).get("imported", 0))
            skipped = int((result or {}).get("skipped", 0))
            job.status = "succeeded"
            job.phase = "completed"
            job.imported = imported
            job.skipped = skipped
            job.processed = imported
            job.total_rows = imported
            job.error = None
            config.last_status = "SUCCESS"
            config.last_imported = imported
            config.last_skipped = skipped
            config.last_error = None


def _remove_manual_source(job: dict) -> None:
    if job["trigger"] != "MANUAL" or not job.get("source_path"):
        return
    try:
        Path(job["source_path"]).unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Could not remove import spool file job_id=%s path=%s",
            job["job_id"],
            job["source_path"],
            exc_info=True,
        )


def process_next_import_job() -> bool:
    """Claim and execute one queued job while holding a cross-process lock."""
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    with engine.connect() as lock_connection:
        locked = lock_connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": IMPORT_LOCK_ID},
        )
        if not locked:
            return False
        job = None
        try:
            job = _claim_next_import_job(worker_id)
            if not job:
                return False
            started = time.monotonic()
            logger.info(
                "Import job started job_id=%s trigger=%s source=%s worker=%s",
                job["job_id"], job["trigger"], job["source_name"], worker_id,
            )
            try:
                source = Path(job["source_path"] or "")
                if not source.is_file():
                    raise FileNotFoundError(f"Không tìm thấy file: {source}")
                if source.suffix.lower() not in {".xlsx", ".csv"}:
                    raise ValueError("File import phải có định dạng .xlsx hoặc .csv")
                with tempfile.TemporaryDirectory(prefix="masterdata-import-") as temp_dir:
                    snapshot = Path(temp_dir) / source.name
                    shutil.copy2(source, snapshot)
                    result = run(
                        str(snapshot),
                        initialize_schema=False,
                        progress_callback=lambda phase, processed, total: _set_job_progress(
                            job["id"], phase, processed, total
                        ),
                    )
                duration = time.monotonic() - started
                _finish_import_job(job["id"], duration, result=result)
                logger.info(
                    "Import job succeeded job_id=%s duration=%.3fs imported=%s skipped=%s",
                    job["job_id"], duration,
                    result.get("imported", 0), result.get("skipped", 0),
                )
            except Exception as exc:
                duration = time.monotonic() - started
                _finish_import_job(job["id"], duration, error=exc)
                logger.exception(
                    "Import job failed job_id=%s duration=%.3fs source=%s error=%s",
                    job["job_id"], duration, job["source_name"], exc,
                )
            finally:
                _remove_manual_source(job)
            return True
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": IMPORT_LOCK_ID},
            )


def recover_interrupted_import() -> bool:
    """Fail orphaned running jobs after a worker dies; queued jobs remain durable."""
    with engine.connect() as connection:
        locked = connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": IMPORT_LOCK_ID},
        )
        if not locked:
            return False
        interrupted_paths: list[str] = []
        try:
            with SessionLocal.begin() as db:
                jobs = db.scalars(
                    select(ImportRunHistory).where(
                        ImportRunHistory.status == "running"
                    )
                ).all()
                if not jobs:
                    queued = db.scalar(
                        select(ImportRunHistory.id)
                        .where(ImportRunHistory.status == "queued")
                        .limit(1)
                    )
                    config = get_import_config(db)
                    was_stale = config.is_running and not queued
                    config.is_running = bool(queued)
                    if was_stale and config.last_status in {"RUNNING", "QUEUED"}:
                        config.last_status = "FAILED"
                        config.last_completed_at = datetime.now(timezone.utc)
                        config.last_error = (
                            "Trạng thái import cũ bị gián đoạn; giao dịch dữ liệu đã được hoàn tác."
                        )
                    return was_stale
                completed_at = datetime.now(timezone.utc)
                message = (
                    "Job import bị gián đoạn khi tiến trình nền dừng; "
                    "giao dịch cơ sở dữ liệu đã được hoàn tác."
                )
                for job in jobs:
                    job.status = "failed"
                    job.phase = "failed"
                    job.completed_at = completed_at
                    job.error = message
                    if job.trigger == "MANUAL" and job.source_path:
                        interrupted_paths.append(job.source_path)
                config = get_import_config(db)
                config.is_running = False
                config.last_status = "FAILED"
                config.last_completed_at = completed_at
                config.last_error = message
            for path in interrupted_paths:
                Path(path).unlink(missing_ok=True)
            logger.warning("Recovered %s interrupted import job(s)", len(jobs))
            return True
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": IMPORT_LOCK_ID},
            )


def _local_now(config: AutoImportConfig) -> datetime:
    try:
        zone = ZoneInfo(config.timezone)
    except ZoneInfoNotFoundError:
        logger.error("Múi giờ auto import không hợp lệ: %s", config.timezone)
        zone = ZoneInfo("UTC")
    return datetime.now(zone)


def enqueue_configured_import(run_key: str) -> ImportRunHistory:
    config = get_import_config()
    return enqueue_import_job(
        config.file_path, "AUTO", Path(config.file_path).name,
        schedule_key=f"AUTO:{run_key}",
    )


def schedule_auto_import_once(last_run_key: str | None) -> str | None:
    """Evaluate the latest DB configuration once and enqueue at most one run."""
    config = get_import_config()
    now = _local_now(config)
    run_key = f"{now.date().isoformat()}:{config.hour:02d}:{config.minute:02d}"
    due = config.enabled and now.hour == config.hour and now.minute == config.minute
    if not due or run_key == last_run_key:
        return last_run_key
    try:
        job = enqueue_configured_import(run_key)
    except ImportAlreadyRunningError:
        # Do not consume this schedule key: retry during the configured minute.
        logger.info(
            "Auto import waiting for active job run_key=%s; will retry in %ss",
            run_key,
            AUTO_POLL_SECONDS,
        )
        return last_run_key
    logger.info("Auto import queued job_id=%s run_key=%s", job.job_id, run_key)
    return run_key


async def import_job_worker() -> None:
    logger.info("Durable import job worker started")
    while True:
        try:
            processed = await asyncio.to_thread(process_next_import_job)
            if not processed:
                await asyncio.sleep(settings.import_job_poll_seconds)
        except Exception:
            logger.exception("Import job worker loop failed; retrying")
            await asyncio.sleep(settings.import_job_poll_seconds)


async def auto_import_worker() -> None:
    logger.info("Job theo dõi cấu hình import tự động đã khởi động")
    last_run_key = None
    while True:
        try:
            last_run_key = schedule_auto_import_once(last_run_key)
        except Exception:
            logger.exception("Không thể tạo job auto import")
        await asyncio.sleep(AUTO_POLL_SECONDS)
