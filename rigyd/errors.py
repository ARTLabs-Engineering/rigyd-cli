from __future__ import annotations


class RigydError(Exception):
    """API/transport error with an optional HTTP status code."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status
