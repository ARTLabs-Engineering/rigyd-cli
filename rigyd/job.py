"""A conversion job — poll to completion, download the MJCF, load into MuJoCo."""

import os
import tempfile
import time
from typing import Callable, Optional

from .cache import job_dir, unzip_and_find
from .client import RigydClient
from .errors import RigydError

_TERMINAL = ("completed", "failed")


class Job:
    def __init__(self, client: RigydClient, data: dict):
        self._client = client
        self._data = data or {}

    # -- state -------------------------------------------------------------
    @property
    def id(self) -> Optional[str]:
        return self._data.get("id")

    @property
    def status(self) -> Optional[str]:
        return self._data.get("status")

    @property
    def progress(self) -> int:
        return self._data.get("progress") or 0

    @property
    def stage(self) -> Optional[str]:
        return self._data.get("stage")

    @property
    def error(self) -> Optional[str]:
        return self._data.get("error")

    @property
    def done(self) -> bool:
        return self.status in _TERMINAL

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"

    def __repr__(self) -> str:
        return f"<rigyd.Job {self.id} status={self.status} progress={self.progress}%>"

    # -- lifecycle ---------------------------------------------------------
    def refresh(self) -> "Job":
        if not self.id:
            raise RigydError(f"Job has no id (response: {self._data})")
        self._data = self._client.get_job(self.id)
        return self

    def wait(self, on_progress: Optional[Callable[["Job"], None]] = None,
             interval: float = 3.0, timeout: float = 1200.0) -> "Job":
        """Poll until completed/failed. Raises RigydError on failure/timeout."""
        elapsed = 0.0
        while elapsed < timeout:
            self.refresh()
            if on_progress:
                on_progress(self)
            if self.done:
                break
            time.sleep(interval)
            elapsed += interval
        if self.status == "failed":
            raise RigydError(self.error or "Conversion failed")
        if not self.succeeded:
            raise RigydError("Timed out waiting for conversion")
        return self

    def download(self, fmt: str = "mjcf", dest: Optional[str] = None) -> str:
        """Download + unzip the result; return the main asset file path
        (the MJCF ``.xml`` for ``fmt='mjcf'``)."""
        if not self.succeeded:
            self.wait()
        dest = dest or job_dir(self.id)
        zip_path = os.path.join(tempfile.gettempdir(), f"rigyd_{self.id}_{fmt}.zip")
        self._client.download_result(self.id, zip_path, fmt)
        return unzip_and_find(zip_path, dest, fmt)

    def load(self, dest: Optional[str] = None):
        """Download the MJCF and return a ``mujoco.MjModel``."""
        import mujoco

        xml_path = self.download("mjcf", dest)
        return mujoco.MjModel.from_xml_path(xml_path)
