"""Windows Service host for the FastAPI backend.

Install from an elevated PowerShell inside the backend virtual environment:
    python windows_service.py --startup auto install
    python windows_service.py start
"""

import os
import subprocess
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil


class MaterialMasterdataService(win32serviceutil.ServiceFramework):
    _svc_name_ = "MaterialMasterdataBackend"
    _svc_display_name_ = "Material Masterdata Portal Backend"
    _svc_description_ = "FastAPI backend for the DOVITEC Material Masterdata Portal."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.process and self.process.poll() is None:
            self.process.terminate()

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("Material Masterdata backend is starting")
        backend_dir = Path(__file__).resolve().parent
        log_dir = backend_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        env = os.environ.copy()
        env.setdefault("PYTHONUNBUFFERED", "1")
        with (log_dir / "backend.log").open("a", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--proxy-headers",
                    "--forwarded-allow-ips",
                    "127.0.0.1",
                ],
                cwd=backend_dir,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            while True:
                wait_result = win32event.WaitForSingleObject(self.stop_event, 2000)
                if wait_result == win32event.WAIT_OBJECT_0:
                    break
                exit_code = self.process.poll()
                if exit_code is not None:
                    raise RuntimeError(f"Uvicorn stopped unexpectedly with exit code {exit_code}")
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    self.process.kill()
        servicemanager.LogInfoMsg("Material Masterdata backend stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(MaterialMasterdataService)
