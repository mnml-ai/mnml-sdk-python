from __future__ import annotations

from typing import Any, Dict, List, Optional


class MnmlError(Exception):
    """An answer that was not a success: the API's own code, message and request id.

    The codes are listed at https://developers.mnml.ai/docs/errors.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        request_id: Optional[str] = None,
        details: Any = None,
        issues: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        super().__init__(message)
        #: The API's error code, such as ``INSUFFICIENT_CREDITS`` or ``RATE_LIMITED``.
        self.code = code
        self.message = message
        #: The HTTP status.
        self.status = status
        #: The ``X-Request-Id`` to quote to support.
        self.request_id = request_id
        self.details = details
        #: On ``VALIDATION_FAILED``, each refused field: ``{"path": ..., "message": ...}``.
        self.issues: List[Dict[str, str]] = issues or []

    def __repr__(self) -> str:
        return f"MnmlError(code={self.code!r}, status={self.status}, request_id={self.request_id!r})"


class MnmlTimeoutError(Exception):
    """``jobs.wait`` ran out of time before the job settled; the job keeps running."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job {job_id} did not finish in time. It is still running; read it again later.")
        self.job_id = job_id
