from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import IO, Any, Callable, Dict, Mapping, Optional, Tuple, Union, cast

from ._errors import MnmlError, MnmlTimeoutError
from .types import Account as AccountData
from .types import Engines as EnginesData
from .types import Job, JobCanceled, JobStarted, RenderStarted, Upload

VERSION = "0.1.0"

DEFAULT_BASE_URL = "https://api.mnml.ai"

#: ``(method, url, headers, body, timeout) -> (status, headers, body)``. Swap it to use your own
#: HTTP stack, or a fake one in tests.
Transport = Callable[[str, str, Dict[str, str], Optional[bytes], float], Tuple[int, Mapping[str, str], bytes]]

_RETRYABLE = {429, 500, 502, 503, 504}
_TERMINAL = {"succeeded", "failed", "canceled"}
#: A longer ``Retry-After`` (a daily limit runs to midnight UTC) is the caller's to handle.
_MAX_RETRY_AFTER = 60.0

FileInput = Union[bytes, str, Path, IO[bytes]]


def _urllib_transport(
    method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout: float
) -> Tuple[int, Mapping[str, str], bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, dict(res.headers), res.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers or {}), err.read()


def _backoff(attempt: int) -> float:
    """0.5 s, 1 s, 2 s ... with a little jitter."""
    return float(0.5 * (1 << attempt)) + random.random() * 0.25


def _read_file(file: FileInput) -> Tuple[bytes, Optional[str]]:
    if isinstance(file, bytes):
        return file, None
    if isinstance(file, (str, Path)):
        path = Path(file)
        return path.read_bytes(), path.name
    return file.read(), os.path.basename(getattr(file, "name", "") or "") or None


class _Resource:
    def __init__(self, client: Mnml) -> None:
        self._client = client


class Renders(_Resource):
    def create(self, *, idempotency_key: Optional[str] = None, **body: Any) -> RenderStarted:
        """Render from a source image (``upload_id``, ``image_url`` or ``job_id``), or a prompt alone.

        ``count`` starts several jobs at once. Fields: https://developers.mnml.ai/docs/renders
        """
        return cast(
            RenderStarted, self._client._request("POST", "/v1/renders", json_body=body, idempotency_key=idempotency_key)
        )


class Edits(_Resource):
    def create(self, *, idempotency_key: Optional[str] = None, **body: Any) -> JobStarted:
        """Edit or erase, over the whole image or a ``region``. https://developers.mnml.ai/docs/edits"""
        return cast(
            JobStarted, self._client._request("POST", "/v1/edits", json_body=body, idempotency_key=idempotency_key)
        )


class Enhancements(_Resource):
    def create(self, *, idempotency_key: Optional[str] = None, **body: Any) -> JobStarted:
        """Upscale, enhance, remove the background or outpaint (``kind``).

        https://developers.mnml.ai/docs/enhancements
        """
        return cast(
            JobStarted,
            self._client._request("POST", "/v1/enhancements", json_body=body, idempotency_key=idempotency_key),
        )


class Videos(_Resource):
    def create(self, *, idempotency_key: Optional[str] = None, **body: Any) -> JobStarted:
        """Video from a still image. https://developers.mnml.ai/docs/videos"""
        return cast(
            JobStarted, self._client._request("POST", "/v1/videos", json_body=body, idempotency_key=idempotency_key)
        )


class Uploads(_Resource):
    def create(
        self,
        file: Optional[FileInput] = None,
        *,
        url: Optional[str] = None,
        filename: Optional[str] = None,
        purpose: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Upload:
        """Upload an image to use as a source or mask (``purpose="mask"``).

        ``file`` is bytes, a path, or an open binary file. Or pass ``url`` to have the API fetch a
        public image.
        """
        if url is not None:
            body: Dict[str, Any] = {"url": url}
            if purpose:
                body["purpose"] = purpose
            return cast(
                Upload, self._client._request("POST", "/v1/uploads", json_body=body, idempotency_key=idempotency_key)
            )
        if file is None:
            raise ValueError("Pass file (bytes, a path or a binary file) or url.")
        data, found_name = _read_file(file)
        name = (filename or found_name or "image").replace('"', "").replace("\r", "").replace("\n", "")
        boundary = uuid.uuid4().hex
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode()
            + data
            + b"\r\n"
        ]
        if purpose:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'.encode()
            )
        parts.append(f"--{boundary}--\r\n".encode())
        return cast(
            Upload,
            self._client._request(
                "POST",
                "/v1/uploads",
                raw_body=b"".join(parts),
                content_type=f"multipart/form-data; boundary={boundary}",
                idempotency_key=idempotency_key,
            ),
        )


class Jobs(_Resource):
    def get(self, job_id: str) -> Job:
        """Read a job."""
        return cast(Job, self._client._request("GET", f"/v1/jobs/{urllib.parse.quote(str(job_id), safe='')}"))

    def cancel(self, job_id: str) -> JobCanceled:
        """Cancel a job. One cancelled before it produced anything is refunded."""
        return cast(
            JobCanceled, self._client._request("POST", f"/v1/jobs/{urllib.parse.quote(str(job_id), safe='')}/cancel")
        )

    def wait(self, job_id: str, *, interval: float = 3.0, timeout: float = 600.0) -> Job:
        """Read the job until it succeeds, fails or is cancelled, and return it.

        Raises MnmlTimeoutError after ``timeout`` seconds; the job keeps running.
        """
        deadline = time.monotonic() + timeout
        while True:
            job = self.get(job_id)
            if job.get("status") in _TERMINAL:
                return job
            if time.monotonic() + interval > deadline:
                raise MnmlTimeoutError(str(job_id))
            self._client._sleep(interval)


class Account(_Resource):
    def get(self) -> AccountData:
        """Balance, tier and limits for this key."""
        return cast(AccountData, self._client._request("GET", "/v1/account"))


class Engines(_Resource):
    def list(self) -> EnginesData:
        """The engines and video models, with their prices and capabilities."""
        return cast(EnginesData, self._client._request("GET", "/v1/engines"))


class Mnml:
    """The mnml API client. Every call returns the answer's ``data``; a refusal raises MnmlError.

    >>> mnml = Mnml()  # reads MNML_API_KEY
    >>> started = mnml.renders.create(prompt="Timber facade, dusk", image_url="https://example.com/a.png")
    >>> job = mnml.jobs.wait(started["id"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 2,
        timeout: float = 60.0,
        transport: Optional[Transport] = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        key = api_key or os.environ.get("MNML_API_KEY")
        if not key:
            raise ValueError("Pass api_key, or set the MNML_API_KEY environment variable.")
        self._api_key = key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._timeout = timeout
        self._transport: Transport = transport or _urllib_transport
        self._sleep = sleep
        self.renders = Renders(self)
        self.edits = Edits(self)
        self.enhancements = Enhancements(self)
        self.videos = Videos(self)
        self.uploads = Uploads(self)
        self.jobs = Jobs(self)
        self.account = Account(self)
        self.engines = Engines(self)

    def __repr__(self) -> str:
        return f"Mnml(base_url={self._base_url!r})"

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        raw_body: Optional[bytes] = None,
        content_type: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "User-Agent": f"mnml-sdk-python/{VERSION}",
        }
        if method == "POST":
            # One key per call, kept across retries, so a retry never charges twice.
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        body = raw_body
        if json_body is not None:
            body = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type

        attempt = 0
        while True:
            try:
                status, res_headers, payload = self._transport(
                    method, f"{self._base_url}{path}", headers, body, self._timeout
                )
            except OSError:
                # A dropped connection, a refused one or a timeout (all OSErrors).
                if attempt >= self._max_retries:
                    raise
                self._sleep(_backoff(attempt))
                attempt += 1
                continue
            lower = {k.lower(): v for k, v in res_headers.items()}
            if status in _RETRYABLE and attempt < self._max_retries:
                try:
                    wait = float(lower.get("retry-after", ""))
                except ValueError:
                    wait = 0.0
                wait = wait if wait > 0 else _backoff(attempt)
                if wait <= _MAX_RETRY_AFTER:
                    self._sleep(wait)
                    attempt += 1
                    continue
            try:
                parsed = json.loads(payload or b"null")
            except ValueError:
                parsed = None
            if 200 <= status < 300 and isinstance(parsed, dict) and parsed.get("success"):
                return parsed["data"]
            error = parsed.get("error") if isinstance(parsed, dict) else None
            error = error if isinstance(error, dict) else {}
            issues = error.get("issues")
            raise MnmlError(
                error.get("code", "HTTP_ERROR"),
                error.get("message", f"The API answered {status}."),
                status,
                lower.get("x-request-id"),
                error.get("details"),
                issues if isinstance(issues, list) else None,
            )
