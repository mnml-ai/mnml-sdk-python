"""Verify webhook deliveries: the Standard Webhooks scheme the API signs with.

``webhook-id``, ``webhook-timestamp``, ``webhook-signature``: an HMAC-SHA256 of
``id.timestamp.body`` under your ``whsec_`` secret. Pass the RAW body, the exact bytes
received before any JSON parsing, or the check fails.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Mapping, Optional, Union, cast

from .types import WebhookEvent

TOLERANCE_SECS = 5 * 60


class WebhookVerificationError(Exception):
    """A delivery whose signature or timestamp does not hold."""


def sign_webhook(secret: str, msg_id: str, timestamp: int, body: Union[str, bytes]) -> str:
    key = base64.b64decode(secret[6:] if secret.startswith("whsec_") else secret)
    payload = body.decode() if isinstance(body, bytes) else body
    mac = hmac.new(key, f"{msg_id}.{timestamp}.{payload}".encode(), hashlib.sha256).digest()
    return "v1," + base64.b64encode(mac).decode()


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    # Case-insensitive, for a plain dict as much as a framework's headers object.
    getter = getattr(headers, "get", None)
    if getter is not None:
        value = getter(name)
        if value is not None:
            return str(value)
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def verify_webhook(
    body: Union[str, bytes],
    headers: Mapping[str, str],
    secret: str,
    now: Optional[float] = None,
) -> WebhookEvent:
    """The parsed event, or WebhookVerificationError when the signature or timestamp does not hold."""
    msg_id = _header(headers, "webhook-id")
    ts = _header(headers, "webhook-timestamp")
    sig = _header(headers, "webhook-signature")
    if not msg_id or not ts or not sig:
        raise WebhookVerificationError("Missing webhook headers.")
    try:
        timestamp = int(ts)
    except ValueError as exc:
        raise WebhookVerificationError("Malformed webhook timestamp.") from exc
    if abs((time.time() if now is None else now) - timestamp) > TOLERANCE_SECS:
        raise WebhookVerificationError("Webhook timestamp is too old or in the future.")
    expected = sign_webhook(secret, msg_id, timestamp, body)
    # The header may carry several space-separated signatures (during a rotation).
    if not any(hmac.compare_digest(candidate, expected) for candidate in sig.split(" ")):
        raise WebhookVerificationError("Webhook signature does not match.")
    return cast(WebhookEvent, json.loads(body))
