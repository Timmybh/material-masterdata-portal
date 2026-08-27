import inspect
import json
import os
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from fastapi import Response
from sqlalchemy.exc import SQLAlchemyError

os.environ["INIT_DB_ON_STARTUP"] = "false"
os.environ["RUN_BACKGROUND_JOBS"] = "false"

from app.db import engine  # noqa: E402
from app.main import app, health, live  # noqa: E402
from app.routers.admin import run_uploaded_import  # noqa: E402
from import_items import run  # noqa: E402


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_):
        return 1


class RuntimeTests(unittest.TestCase):
    def test_capacity_defaults(self):
        self.assertEqual(engine.pool.size(), 5)
        self.assertEqual(engine.pool._max_overflow, 5)

    def test_import_does_not_initialize_schema_by_default(self):
        parameter = inspect.signature(run).parameters["initialize_schema"]
        self.assertIs(parameter.default, False)

    def test_liveness_does_not_require_database(self):
        self.assertEqual(live()["status"], "ok")

    def test_readiness_checks_database(self):
        response = Response()
        with patch("app.main.engine.connect", return_value=_Connection()):
            result = health(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(result["database"], "connected")

    def test_readiness_reports_database_failure(self):
        response = Response()
        with patch("app.main.engine.connect", side_effect=SQLAlchemyError("down")):
            result = health(response)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(result["database"], "unavailable")

    def test_logging_configuration_is_valid_json(self):
        logging_path = Path(__file__).resolve().parents[1] / "logging.json"
        config = json.loads(logging_path.read_text(encoding="utf-8"))
        self.assertIn("uvicorn.access", config["loggers"])

    def test_application_version(self):
        self.assertEqual(app.version, "1.6.9")

    def test_manual_import_returns_before_background_processing(self):
        route = next(route for route in app.routes if route.path == "/api/admin/item-import/upload")
        self.assertEqual(route.status_code, 202)

    def test_uploaded_import_removes_temporary_file_on_failure(self):
        with NamedTemporaryFile(delete=False) as source:
            path = Path(source.name)
        with patch("app.routers.admin.execute_import", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                run_uploaded_import(path)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
