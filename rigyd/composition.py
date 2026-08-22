"""A SimReady Asset Composer workflow and its linked conversion job."""

import time
from typing import Callable, Optional

from .client import RigydClient
from .errors import RigydError
from .job import Job

_TERMINAL = ("ready", "completed", "failed", "cancelled")


class Composition:
    def __init__(self, client: RigydClient, data: dict):
        self._client = client
        self._data = data or {}

    @property
    def id(self) -> Optional[str]:
        return self._data.get("id")

    @property
    def workflow(self) -> dict:
        return self._data.get("workflow") or {}

    @property
    def status(self) -> Optional[str]:
        return self.workflow.get("status")

    @property
    def stage(self) -> Optional[str]:
        return self.workflow.get("stage")

    @property
    def progress(self) -> int:
        return self.workflow.get("progress") or 0

    @property
    def error(self) -> Optional[str]:
        return self.workflow.get("error")

    @property
    def conversion_job_id(self) -> Optional[str]:
        return self._data.get("conversion_job_id")

    @property
    def done(self) -> bool:
        return self.status in _TERMINAL

    def __repr__(self) -> str:
        return (f"<rigyd.Composition {self.id} status={self.status} "
                f"stage={self.stage} progress={self.progress}%>")

    def refresh(self) -> "Composition":
        if not self.id:
            raise RigydError(f"Composition has no id (response: {self._data})")
        self._data = self._client.get_composition(self.id)
        return self

    def wait(self, on_progress: Optional[Callable[["Composition"], None]] = None,
             interval: float = 3.0, timeout: float = 1800.0) -> "Composition":
        """Poll until ready/completed/failed/cancelled."""
        elapsed = 0.0
        while elapsed < timeout:
            self.refresh()
            if on_progress:
                on_progress(self)
            if self.done:
                break
            time.sleep(interval)
            elapsed += interval
        if self.status in ("failed", "cancelled"):
            raise RigydError(self.error or f"Composition {self.status}")
        if not self.done:
            raise RigydError("Timed out waiting for composition")
        return self

    def submit(self) -> Job:
        """Submit a ready prototype to SimReady and return its conversion job."""
        if not self.id:
            raise RigydError(f"Composition has no id (response: {self._data})")
        return Job(self._client, self._client.submit_composition(self.id))

    def conversion_job(self, refresh: bool = True) -> Job:
        """Return the conversion linked by ``conversion_job_id``."""
        if not self.conversion_job_id:
            raise RigydError("Composition has no conversion job yet")
        job = Job(self._client, {"id": self.conversion_job_id})
        return job.refresh() if refresh else job
