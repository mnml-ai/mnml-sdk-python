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
from typing import IO, Any, Callable, Dict, List, Literal, Mapping, Optional, Sequence, Tuple, Union, cast

from ._errors import MnmlError, MnmlTimeoutError
from .types import Account as AccountData
from .types import (
    AspectRatio,
    CameraMove,
    DownloadedFile,
    EditKind,
    EngineId,
    EnhancementKind,
    Frame,
    Job,
    JobCanceled,
    JobOutput,
    JobStarted,
    Mode,
    OutpaintAspectRatio,
    Reference,
    Region,
    RenderStarted,
    Upload,
    UploadPurpose,
    VideoModelId,
    VideoMotion,
)
from .types import Engines as EnginesData

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


def _fields(scope: Dict[str, Any]) -> Dict[str, Any]:
    """A create call's body: its keyword arguments, less the client's own and the unset ones."""
    return {
        k: (dict(v) if isinstance(v, Mapping) else list(v) if isinstance(v, (list, tuple)) else v)
        for k, v in scope.items()
        if k not in _NOT_FIELDS and v is not None
    }


_NOT_FIELDS = {"self", "idempotency_key", "interval", "timeout"}

#: An engine id from ``engines.list()``, or its display name.
EngineArg = Union[EngineId, str, None]


class _Resource:
    def __init__(self, client: Mnml) -> None:
        self._client = client


class Renders(_Resource):
    def create(
        self,
        *,
        prompt: str,
        engine: EngineArg = None,
        mode: Optional[Mode] = None,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        references: Optional[Sequence[Reference]] = None,
        settings: Optional[Mapping[str, str]] = None,
        aspect_ratio: Optional[AspectRatio] = None,
        count: Optional[int] = None,
        seed: Optional[int] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> RenderStarted:
        """Render from a source image (``upload_id``, ``image_url`` or ``job_id``), or a prompt alone.

        ``count`` (1-4) starts several jobs at once, each its own charge. ``settings`` are Studio's
        settings for the engine and mode, name to value. https://developers.mnml.ai/docs/renders
        """
        body = _fields(locals())
        return cast(
            RenderStarted, self._client._request("POST", "/v1/renders", json_body=body, idempotency_key=idempotency_key)
        )

    def create_and_wait(
        self,
        *,
        prompt: str,
        engine: EngineArg = None,
        mode: Optional[Mode] = None,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        references: Optional[Sequence[Reference]] = None,
        settings: Optional[Mapping[str, str]] = None,
        aspect_ratio: Optional[AspectRatio] = None,
        count: Optional[int] = None,
        seed: Optional[int] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        interval: float = 3.0,
        timeout: float = 600.0,
    ) -> List[Job]:
        """``create``, then wait for every job it started: one per ``count``."""
        body = _fields(locals())
        started = self.create(idempotency_key=idempotency_key, **body)
        return self._client.jobs.wait_all(started["ids"], interval=interval, timeout=timeout)


class Edits(_Resource):
    def create(
        self,
        *,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        kind: Optional[EditKind] = None,
        prompt: Optional[str] = None,
        engine: EngineArg = None,
        mode: Optional[Mode] = None,
        references: Optional[Sequence[Reference]] = None,
        region: Optional[Region] = None,
        mask_upload_id: Optional[str] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> JobStarted:
        """Change one thing and keep the rest: over the whole image, a ``region`` or a mask.

        ``kind="erase"`` removes what the area covers, and takes no prompt. ``mask_upload_id`` is an
        upload made with ``purpose="mask"``: white to change, black to keep.
        https://developers.mnml.ai/docs/edits
        """
        body = _fields(locals())
        return cast(
            JobStarted, self._client._request("POST", "/v1/edits", json_body=body, idempotency_key=idempotency_key)
        )

    def create_and_wait(
        self,
        *,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        kind: Optional[EditKind] = None,
        prompt: Optional[str] = None,
        engine: EngineArg = None,
        mode: Optional[Mode] = None,
        references: Optional[Sequence[Reference]] = None,
        region: Optional[Region] = None,
        mask_upload_id: Optional[str] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        interval: float = 3.0,
        timeout: float = 600.0,
    ) -> Job:
        """``create``, then wait for the job to settle."""
        body = _fields(locals())
        started = self.create(idempotency_key=idempotency_key, **body)
        return self._client.jobs.wait(started["id"], interval=interval, timeout=timeout)


class Enhancements(_Resource):
    def create(
        self,
        *,
        kind: EnhancementKind,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        creativity: Optional[int] = None,
        prompt: Optional[str] = None,
        aspect_ratio: Optional[OutpaintAspectRatio] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> JobStarted:
        """Upscale, enhance, remove the background or outpaint (``kind``).

        ``creativity`` (0-100) and ``prompt`` are for ``enhance``; ``aspect_ratio`` (required) and
        ``prompt`` for ``outpaint``. https://developers.mnml.ai/docs/enhancements
        """
        body = _fields(locals())
        return cast(
            JobStarted,
            self._client._request("POST", "/v1/enhancements", json_body=body, idempotency_key=idempotency_key),
        )

    def create_and_wait(
        self,
        *,
        kind: EnhancementKind,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        creativity: Optional[int] = None,
        prompt: Optional[str] = None,
        aspect_ratio: Optional[OutpaintAspectRatio] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        interval: float = 3.0,
        timeout: float = 600.0,
    ) -> Job:
        """``create``, then wait for the job to settle."""
        body = _fields(locals())
        started = self.create(idempotency_key=idempotency_key, **body)
        return self._client.jobs.wait(started["id"], interval=interval, timeout=timeout)


class Videos(_Resource):
    def create(
        self,
        *,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        model: Union[VideoModelId, str, None] = None,
        duration_seconds: Optional[int] = None,
        camera_movement: Union[Literal["static", "auto"], CameraMove, str, None] = None,
        motion: Optional[VideoMotion] = None,
        prompt: Optional[str] = None,
        end_frame: Optional[Frame] = None,
        cinematic: Optional[bool] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> JobStarted:
        """Video from a still image: the first frame.

        ``model`` defaults to ``v2.0-flash``; ``duration_seconds`` is 10 or 15 on the v2.0 models.
        ``camera_movement`` is ``static`` (the default), ``auto``, or one or two moves joined by a
        comma: ``"dolly-in,tilt-up"``. https://developers.mnml.ai/docs/videos
        """
        body = _fields(locals())
        return cast(
            JobStarted, self._client._request("POST", "/v1/videos", json_body=body, idempotency_key=idempotency_key)
        )

    def create_and_wait(
        self,
        *,
        upload_id: Optional[str] = None,
        image_url: Optional[str] = None,
        job_id: Optional[str] = None,
        model: Union[VideoModelId, str, None] = None,
        duration_seconds: Optional[int] = None,
        camera_movement: Union[Literal["static", "auto"], CameraMove, str, None] = None,
        motion: Optional[VideoMotion] = None,
        prompt: Optional[str] = None,
        end_frame: Optional[Frame] = None,
        cinematic: Optional[bool] = None,
        webhook_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        interval: float = 10.0,
        timeout: float = 1200.0,
    ) -> Job:
        """``create``, then wait for the clip. A clip takes minutes, so this reads every 10 s."""
        body = _fields(locals())
        started = self.create(idempotency_key=idempotency_key, **body)
        return self._client.jobs.wait(started["id"], interval=interval, timeout=timeout)


class Uploads(_Resource):
    def create(
        self,
        file: Optional[FileInput] = None,
        *,
        url: Optional[str] = None,
        filename: Optional[str] = None,
        purpose: Optional[UploadPurpose] = None,
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


def _job_path(job_id: str) -> str:
    return f"/v1/jobs/{urllib.parse.quote(str(job_id), safe='')}"


class Jobs(_Resource):
    def get(self, job_id: str) -> Job:
        """Read a job."""
        return cast(Job, self._client._request("GET", _job_path(job_id)))

    def cancel(self, job_id: str) -> JobCanceled:
        """Cancel a job. One cancelled before it produced anything is refunded."""
        return cast(JobCanceled, self._client._request("POST", f"{_job_path(job_id)}/cancel"))

    def wait(self, job_id: str, *, interval: float = 3.0, timeout: float = 600.0) -> Job:
        """Read the job until it succeeds, fails or is cancelled, and return it.

        Raises MnmlTimeoutError after ``timeout`` seconds; the job keeps running.
        """
        return self.wait_all([job_id], interval=interval, timeout=timeout)[0]

    def wait_all(self, job_ids: Sequence[str], *, interval: float = 3.0, timeout: float = 600.0) -> List[Job]:
        """``wait`` for several jobs at once, such as every id a render with ``count`` started.

        Returns them in the order given. Raises MnmlTimeoutError, naming the first job still
        running, after ``timeout`` seconds.
        """
        deadline = time.monotonic() + timeout
        done: Dict[str, Job] = {}
        while True:
            for job_id in job_ids:
                if job_id not in done:
                    job = self.get(job_id)
                    if job.get("status") in _TERMINAL:
                        done[job_id] = job
            pending = [job_id for job_id in job_ids if job_id not in done]
            if not pending:
                return [done[job_id] for job_id in job_ids]
            if time.monotonic() + interval > deadline:
                raise MnmlTimeoutError(str(pending[0]))
            self._client._sleep(interval)


class Files(_Resource):
    def download(self, output: Union[JobOutput, str], *, to: Union[str, Path, None] = None) -> DownloadedFile:
        """The file behind a job output (or its ``url``): its bytes and content type.

        Pass ``to`` to also write it to that path. The link's signature is its credential, so your
        key is not sent with it. An expired link raises MnmlError with ``NOT_FOUND``: read the job
        again for fresh links.
        """
        url = output if isinstance(output, str) else output["url"]
        status, headers, payload = self._client._send("GET", url, self._client._base_headers(), None)
        if not 200 <= status < 300:
            raise _error_from(status, headers, payload)
        if to is not None:
            Path(to).write_bytes(payload)
        return {"data": payload, "content_type": headers.get("content-type")}


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
        self.files = Files(self)
        self.account = Account(self)
        self.engines = Engines(self)

    def __repr__(self) -> str:
        return f"Mnml(base_url={self._base_url!r})"

    def _base_headers(self) -> Dict[str, str]:
        return {"User-Agent": f"mnml-sdk-python/{VERSION}"}

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
            **self._base_headers(),
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
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

        status, res_headers, payload = self._send(method, f"{self._base_url}{path}", headers, body)
        parsed = _parse(payload)
        if 200 <= status < 300 and isinstance(parsed, dict) and parsed.get("success"):
            return parsed["data"]
        raise _error_from(status, res_headers, payload)

    def _send(
        self, method: str, url: str, headers: Dict[str, str], body: Optional[bytes]
    ) -> Tuple[int, Dict[str, str], bytes]:
        """One call with the client's retries: a 429, a 5xx or a dropped connection is sent again
        (the same headers, so the same idempotency key) after ``Retry-After`` or a backoff. The
        last answer is returned, whatever it is, with its headers' names in lower case."""
        attempt = 0
        while True:
            try:
                status, res_headers, payload = self._transport(method, url, headers, body, self._timeout)
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
            return status, lower, payload


def _parse(payload: bytes) -> Any:
    try:
        return json.loads(payload or b"null")
    except ValueError:
        return None


def _error_from(status: int, headers: Mapping[str, str], payload: bytes) -> MnmlError:
    """A refusal as MnmlError, from the API's error envelope when the answer has one."""
    parsed = _parse(payload)
    error = parsed.get("error") if isinstance(parsed, dict) else None
    error = error if isinstance(error, dict) else {}
    issues = error.get("issues")
    return MnmlError(
        error.get("code", "HTTP_ERROR"),
        error.get("message", f"The API answered {status}."),
        status,
        headers.get("x-request-id"),
        error.get("details"),
        issues if isinstance(issues, list) else None,
    )
