import os
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

os.environ["INIT_DB_ON_STARTUP"] = "false"
os.environ["RUN_BACKGROUND_JOBS"] = "false"

from app.auto_import import (  # noqa: E402
    ImportAlreadyRunningError,
    _finish_import_job,
    enqueue_import_job,
    process_next_import_job,
    schedule_auto_import_once,
)
from app.models import AutoImportConfig, ImportRunHistory  # noqa: E402
from app.routers.admin import read_item_import_job  # noqa: E402
from import_items import run  # noqa: E402


class _Context:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *_):
        return False


class _LockConnection:
    def __init__(self, locked=True):
        self.locked = locked
        self.unlock_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def scalar(self, *_args, **_kwargs):
        return self.locked

    def execute(self, *_args, **_kwargs):
        self.unlock_calls += 1


class ImportJobTests(unittest.TestCase):
    def _job(self, path):
        return {
            "id": 7,
            "job_id": uuid.uuid4(),
            "trigger": "MANUAL",
            "source_name": Path(path).name,
            "source_path": str(path),
        }

    def test_successful_job_records_counts_and_duration(self):
        with NamedTemporaryFile(suffix=".csv") as source:
            job = self._job(source.name)
            connection = _LockConnection()
            with (
                patch("app.auto_import.engine.connect", return_value=connection),
                patch("app.auto_import._claim_next_import_job", return_value=job),
                patch("app.auto_import.run", return_value={"imported": 23039, "skipped": 4}),
                patch("app.auto_import._finish_import_job") as finish,
                patch("app.auto_import._remove_manual_source"),
                patch("app.auto_import.time.monotonic", side_effect=[10.0, 62.0]),
            ):
                processed = process_next_import_job()

        self.assertTrue(processed)
        finish.assert_called_once_with(
            7, 52.0, result={"imported": 23039, "skipped": 4}
        )
        self.assertEqual(connection.unlock_calls, 1)

    def test_failed_job_is_marked_failed_and_lock_is_released(self):
        with NamedTemporaryFile(suffix=".csv") as source:
            job = self._job(source.name)
            connection = _LockConnection()
            failure = RuntimeError("duplicate item code")
            with (
                patch("app.auto_import.engine.connect", return_value=connection),
                patch("app.auto_import._claim_next_import_job", return_value=job),
                patch("app.auto_import.run", side_effect=failure),
                patch("app.auto_import._finish_import_job") as finish,
                patch("app.auto_import._remove_manual_source"),
                patch("app.auto_import.time.monotonic", side_effect=[20.0, 23.5]),
            ):
                processed = process_next_import_job()

        self.assertTrue(processed)
        finish.assert_called_once_with(7, 3.5, error=failure)
        self.assertEqual(connection.unlock_calls, 1)

    def test_finish_persists_success_counts_and_failure_error(self):
        job = SimpleNamespace(status="running")
        config = SimpleNamespace()

        class FinishDatabase:
            def get(self, model, _key):
                return config if model is AutoImportConfig else job

        session_factory = MagicMock()
        session_factory.begin.return_value = _Context(FinishDatabase())
        with patch("app.auto_import.SessionLocal", session_factory):
            _finish_import_job(1, 52.125, result={"imported": 23039, "skipped": 7})

        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.imported, 23039)
        self.assertEqual(job.skipped, 7)
        self.assertEqual(job.duration_seconds, 52.125)
        self.assertEqual(config.last_status, "SUCCESS")

        failure = RuntimeError("insert failed; transaction rolled back")
        with patch("app.auto_import.SessionLocal", session_factory):
            _finish_import_job(1, 3.0, error=failure)

        self.assertEqual(job.status, "failed")
        self.assertIn("transaction rolled back", job.error)
        self.assertEqual(config.last_status, "FAILED")

    def test_database_error_during_replace_uses_transaction_rollback(self):
        class FailingDatabase:
            def __init__(self):
                self.calls = 0

            def execute(self, _statement):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("insert failed")

        class Transaction:
            def __init__(self):
                self.database = FailingDatabase()
                self.rolled_back = False

            def __enter__(self):
                return self.database

            def __exit__(self, exception_type, *_):
                self.rolled_back = exception_type is not None
                return False

        transaction = Transaction()
        session_factory = MagicMock()
        session_factory.begin.return_value = transaction
        with NamedTemporaryFile("w", suffix=".csv", encoding="utf-8", delete=False) as source:
            source.write("Id,Code,Name,ItemTypeName\n1,A001,But bi,CCDC\n")
            source_path = Path(source.name)
        try:
            with patch("import_items.SessionLocal", session_factory):
                with self.assertRaisesRegex(RuntimeError, "insert failed"):
                    run(str(source_path))
        finally:
            source_path.unlink(missing_ok=True)

        self.assertTrue(transaction.rolled_back)

    def test_duplicate_enqueue_is_rejected_across_process_boundary(self):
        class FailingEnqueueDatabase:
            def add(self, _job):
                pass

            def flush(self):
                raise IntegrityError("insert", {}, RuntimeError("unique active job"))

        active_job = SimpleNamespace(job_id=uuid.uuid4())
        active_database = SimpleNamespace(scalar=lambda _statement: active_job)
        session_factory = MagicMock()
        session_factory.begin.return_value = _Context(FailingEnqueueDatabase())
        session_factory.return_value = _Context(active_database)

        with patch("app.auto_import.SessionLocal", session_factory):
            with self.assertRaises(ImportAlreadyRunningError):
                enqueue_import_job("items.xlsx", "MANUAL")

    def test_polling_endpoint_returns_persisted_job(self):
        job_id = uuid.uuid4()
        job = ImportRunHistory(
            id=1,
            job_id=job_id,
            trigger="MANUAL",
            source_name="items.xlsx",
            status="running",
            phase="importing",
            queued_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            processed=12000,
            total_rows=23039,
        )
        database = SimpleNamespace(scalar=lambda _statement: job)

        result = read_item_import_job(job_id, db=database, _=None)

        self.assertIs(result, job)
        self.assertEqual(result.processed, 12000)
        self.assertEqual(result.total_rows, 23039)

    def test_auto_scheduler_reads_db_config_and_respects_enabled_flag(self):
        disabled = SimpleNamespace(
            enabled=False, hour=19, minute=0, timezone="UTC", file_path="items.xlsx"
        )
        enabled = SimpleNamespace(
            enabled=True, hour=19, minute=0, timezone="UTC", file_path="items.xlsx"
        )
        now = datetime(2026, 8, 31, 19, 0, tzinfo=timezone.utc)
        queued_job = SimpleNamespace(job_id=uuid.uuid4())
        with (
            patch("app.auto_import.get_import_config", side_effect=[disabled, enabled]) as read_config,
            patch("app.auto_import._local_now", return_value=now),
            patch("app.auto_import.enqueue_configured_import", return_value=queued_job) as enqueue,
        ):
            last_run_key = schedule_auto_import_once(None)
            last_run_key = schedule_auto_import_once(last_run_key)

        self.assertEqual(read_config.call_count, 2)
        enqueue.assert_called_once_with("2026-08-31:19:00")
        self.assertEqual(last_run_key, "2026-08-31:19:00")

    def test_auto_scheduler_does_not_run_outside_configured_minute(self):
        config = SimpleNamespace(
            enabled=True, hour=19, minute=0, timezone="UTC", file_path="items.xlsx"
        )
        with (
            patch("app.auto_import.get_import_config", return_value=config),
            patch(
                "app.auto_import._local_now",
                return_value=datetime(2026, 8, 31, 18, 59, tzinfo=timezone.utc),
            ),
            patch("app.auto_import.enqueue_configured_import") as enqueue,
        ):
            last_run_key = schedule_auto_import_once(None)

        enqueue.assert_not_called()
        self.assertIsNone(last_run_key)

    def test_auto_scheduler_retries_active_job_conflict_during_due_minute(self):
        config = SimpleNamespace(
            enabled=True, hour=19, minute=0, timezone="UTC", file_path="items.xlsx"
        )
        with (
            patch("app.auto_import.get_import_config", return_value=config),
            patch(
                "app.auto_import._local_now",
                return_value=datetime(2026, 8, 31, 19, 0, tzinfo=timezone.utc),
            ),
            patch(
                "app.auto_import.enqueue_configured_import",
                side_effect=ImportAlreadyRunningError("active"),
            ) as enqueue,
        ):
            first_result = schedule_auto_import_once(None)
            second_result = schedule_auto_import_once(first_result)

        self.assertEqual(enqueue.call_count, 2)
        self.assertIsNone(second_result)


if __name__ == "__main__":
    unittest.main()
