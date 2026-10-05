"""The mnml API's answers, as its OpenAPI document (``spec/openapi.json``) states them.

They are ``TypedDict`` s: every call returns a plain ``dict``, and these name its keys for your
editor and type checker. ``tests/test_spec.py`` checks each one against the document.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class JobStarted(TypedDict):
    id: str
    status: str
    credits_charged: int
    #: True when this answers an earlier identical request: nothing new was charged.
    replayed: bool
    notes: List[str]


class RenderStarted(JobStarted):
    #: Every job the call started; ``id`` is the first.
    ids: List[str]


class JobOutput(TypedDict):
    url: str
    media: str
    expires_at: str


class JobError(TypedDict):
    code: str
    message: str


class Job(TypedDict):
    id: str
    #: ``queued``, ``processing``, ``succeeded``, ``failed`` or ``canceled``.
    status: str
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
    #: ``refunded``, ``requested``, ``too-late`` or ``already-settled``.
    outcome: str
    credits_refunded: int


class Upload(TypedDict):
    id: str
    width: Optional[int]
    height: Optional[int]
    size_bytes: int
    purpose: str
    created_at: str


class Account(TypedDict):
    id: str
    email: str
    name: Optional[str]
    tier: str
    credits: Dict[str, int]
    key: Dict[str, Any]
    limits: Dict[str, Any]


class Engines(TypedDict):
    engines: List[Dict[str, Any]]
    video_models: List[Dict[str, Any]]


class WebhookEvent(TypedDict):
    #: ``job.succeeded``, ``job.failed``, ``job.canceled``, ``credits.low`` or ``webhook.test``.
    type: str
    timestamp: str
    #: The job, as ``jobs.get`` returns it, for ``job.*`` events.
    data: Any
