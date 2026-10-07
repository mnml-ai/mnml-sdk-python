"""The mnml API's requests and answers, as its OpenAPI document (``spec/openapi.json``) states them.

They are ``TypedDict`` s: every call returns a plain ``dict``, and these name its keys for your
editor and type checker. ``tests/test_spec.py`` checks each one against the document.
"""

from __future__ import annotations

import os
from typing import IO, List, Literal, Optional, Tuple, TypedDict, Union

Mode = Literal["exterior", "interior", "masterplan", "plan", "landscape", "product", "text-to-render"]

AspectRatio = Literal["auto", "1:1", "3:2", "4:3", "5:4", "16:9", "21:9", "2:3", "3:4", "4:5", "9:16"]

#: The frames ``outpaint`` extends to: every aspect ratio but ``auto``.
OutpaintAspectRatio = Literal["1:1", "3:2", "4:3", "5:4", "16:9", "21:9", "2:3", "3:4", "4:5", "9:16"]

#: The engines a render or edit can name today. ``engines.list()`` is the live list, with prices
#: and what each one can do; an engine's display name (``"v4.6"``) works as well as its id.
EngineId = Literal["v4.6-ultra", "v4.5-ultra", "v4.5-fast", "v4.4-ultra", "v4.4-fast", "v4.3", "v4.3-fast", "v3.1"]

#: The video models. A model's name (``"v2.0 Flash"``) works as well as its id.
VideoModelId = Literal["v2.0-flash", "v2.0", "v1.1"]

#: One camera move. ``camera_movement`` is ``static`` (the default), ``auto`` to let the prompt
#: decide, one move, or two joined by a comma: ``"dolly-in,tilt-up"``.
CameraMove = Literal[
    "dolly-in",
    "dolly-out",
    "truck-left",
    "truck-right",
    "pedestal-up",
    "pedestal-down",
    "pan-left",
    "pan-right",
    "tilt-up",
    "tilt-down",
    "orbit-left",
    "orbit-right",
    "zoom-in",
    "zoom-out",
]

#: How much moves in the scene. ``subtle`` is the default; ``auto`` lets the prompt decide.
VideoMotion = Literal["subtle", "balanced", "dynamic", "auto"]

ReferenceMode = Literal["auto", "style", "material", "atmosphere", "color", "geometry"]

EnhancementKind = Literal["upscale", "enhance", "bg-remove", "outpaint"]

EditKind = Literal["edit", "erase"]

UploadPurpose = Literal["image", "mask"]

JobStatus = Literal["queued", "processing", "succeeded", "failed", "canceled"]


# --- What you send --------------------------------------------------------------------------

#: An image, sent in the call. A ``str`` is sent as it is: a public ``https://`` link, a
#: ``data:image/...;base64,`` URI or bare base64. Bytes, a path or an open binary file is read and
#: sent as a data URI. A ``str`` is never read as a path: pass ``Path("house.jpg")`` for a file.
ImageInput = Union[str, bytes, bytearray, memoryview, os.PathLike[str], IO[bytes]]


class Frame(TypedDict, total=False):
    """An image: exactly one of ``image``, your upload, or a finished job."""

    image: ImageInput
    upload_id: str
    job_id: str
    #: Deprecated: the old name of ``image``, still taken.
    image_url: str


class Reference(Frame, total=False):
    """An image whose style, materials, mood or geometry to follow."""

    mode: ReferenceMode


class Box(TypedDict):
    """x, y of the top-left corner, width and height, all fractions (0-1) of the image."""

    x: float
    y: float
    width: float
    height: float


class Region(TypedDict, total=False):
    """An area of the image: a ``box``, or a ``polygon`` of 3 to 64 ``(x, y)`` points (0-1)."""

    box: Box
    polygon: List[Tuple[float, float]]


# --- What you get back ----------------------------------------------------------------------


class JobStarted(TypedDict):
    id: str
    status: str
    credits_charged: int
    #: True when this answers an earlier identical request: nothing new was charged.
    replayed: bool
    #: What the API changed or dropped from the request, said back instead of silently.
    notes: List[str]


class _RenderStartedFields(JobStarted):
    #: Every job the call started; ``id`` is the first.
    ids: List[str]


class RenderStarted(_RenderStartedFields, total=False):
    #: Only with ``wait``: every job as ``jobs.get`` reads it, outputs included. Each one settled
    #: when the wait ended; otherwise some are still running.
    jobs: List[Job]


class JobOutput(TypedDict):
    #: A signed link, served by the API. Download it before ``expires_at``.
    url: str
    media: Literal["image", "video"]
    expires_at: str


class JobError(TypedDict):
    code: Literal["UNSAFE_CONTENT", "NO_CHANGE", "CANCELED", "RENDER_FAILED"]
    message: str


class Job(TypedDict):
    id: str
    status: JobStatus
    kind: str
    engine: Optional[str]
    outputs: List[JobOutput]
    credits_charged: int
    credits_refunded: int
    error: Optional[JobError]
    created_at: str
    completed_at: Optional[str]


class JobCanceled(TypedDict):
    id: str
    outcome: Literal["refunded", "requested", "too-late", "already-settled"]
    credits_refunded: int


class Upload(TypedDict):
    id: str
    width: Optional[int]
    height: Optional[int]
    size_bytes: int
    purpose: UploadPurpose
    created_at: str


class AccountCredits(TypedDict):
    #: What the next call can spend.
    spendable: int


class AccountKey(TypedDict):
    id: str
    allowed_origins: List[str]
    #: Your own daily limit for this key, or None for none.
    daily_credit_limit: Optional[int]


class AccountLimits(TypedDict):
    #: Shared by every key on the account (free), or this key's own (paid).
    scope: Literal["account", "key"]
    requests_per_minute: int
    #: GET requests (job polls included), counted apart from the rest.
    reads_per_minute: int
    concurrent_jobs: int
    #: Credits this key may still spend per UTC day; None is no limit.
    daily_credits: Optional[int]


class Account(TypedDict):
    id: str
    email: str
    name: Optional[str]
    #: ``paid`` once the account has bought credits; it sets the limits.
    tier: Literal["free", "paid"]
    credits: AccountCredits
    key: AccountKey
    limits: AccountLimits


class EnginePrices(TypedDict):
    #: Credits for one render.
    render: int
    #: Credits for one edit.
    edit: int


class EngineCapabilities(TypedDict):
    text_to_render: bool
    masks: bool
    edit_references: bool
    max_references: int


class Engine(TypedDict):
    id: str
    name: str
    tier: Literal["primary", "legacy"]
    default: bool
    paid_only: bool
    #: Whether this account may use it now (a paid-only engine needs a paid account).
    available: bool
    prices: EnginePrices
    capabilities: EngineCapabilities


class VideoPrice(TypedDict):
    #: None is the model's one fixed length.
    duration_seconds: Optional[int]
    credits: int


class VideoModel(TypedDict):
    id: str
    #: Pass this, or the id, as ``model``.
    name: str
    default: bool
    available: bool
    prices: List[VideoPrice]


class Engines(TypedDict):
    engines: List[Engine]
    video_models: List[VideoModel]


class DownloadedFile(TypedDict):
    data: bytes
    #: ``image/jpeg``, ``image/png``, ``image/webp`` or ``video/mp4``.
    content_type: Optional[str]


# --- Webhooks -------------------------------------------------------------------------------


class CreditsLow(TypedDict):
    """``credits.low``: the balance fell under the threshold (sent at most once a day)."""

    balance: int
    threshold: int


class WebhookTest(TypedDict):
    message: str


class JobEvent(TypedDict):
    type: Literal["job.succeeded", "job.failed", "job.canceled"]
    #: ISO 8601.
    timestamp: str
    #: The job, as ``jobs.get`` returns it.
    data: Job


class CreditsLowEvent(TypedDict):
    type: Literal["credits.low"]
    timestamp: str
    data: CreditsLow


class WebhookTestEvent(TypedDict):
    type: Literal["webhook.test"]
    timestamp: str
    data: WebhookTest


#: A webhook message. Check ``event["type"]`` and your type checker narrows ``event["data"]``.
#: New types may be added, so ignore one you do not handle.
WebhookEvent = Union[JobEvent, CreditsLowEvent, WebhookTestEvent]
