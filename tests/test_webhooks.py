from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os

import pytest

from mnml_ai import WebhookVerificationError, sign_webhook, verify_webhook

# A throwaway secret made fresh for every run: no secret, real or sample, lives in this repo.
KEY = os.urandom(24)
SECRET = "whsec_" + base64.b64encode(KEY).decode()
NOW = 1_791_000_000
BODY = json.dumps({"type": "job.succeeded", "timestamp": "2026-10-04T12:00:00Z", "data": {"id": "42"}})


def headers(body: str = BODY, ts: int = NOW) -> dict:
    return {
        "webhook-id": "msg_1",
        "webhook-timestamp": str(ts),
        "webhook-signature": sign_webhook(SECRET, "msg_1", ts, body),
    }


def test_signs_as_standard_webhooks_does() -> None:
    # HMAC-SHA256 of id.timestamp.body under the decoded secret; the whsec_ prefix is optional.
    expected = "v1," + base64.b64encode(hmac.new(KEY, b'msg_1.1614265330.{"test":1}', hashlib.sha256).digest()).decode()
    assert sign_webhook(SECRET, "msg_1", 1614265330, '{"test":1}') == expected
    assert sign_webhook(base64.b64encode(KEY).decode(), "msg_1", 1614265330, '{"test":1}') == expected


def test_returns_the_event_for_a_genuine_delivery_from_str_or_bytes() -> None:
    assert verify_webhook(BODY, headers(), SECRET, now=NOW)["data"] == {"id": "42"}
    assert verify_webhook(BODY.encode(), headers(), SECRET, now=NOW)["type"] == "job.succeeded"


def test_reads_headers_in_any_case() -> None:
    upper = {k.title(): v for k, v in headers().items()}
    assert verify_webhook(BODY, upper, SECRET, now=NOW)["type"] == "job.succeeded"


def test_accepts_any_one_of_several_signatures() -> None:
    h = headers()
    h["webhook-signature"] = f"v1,bm90IGl0 {h['webhook-signature']}"
    verify_webhook(BODY, h, SECRET, now=NOW)


@pytest.mark.parametrize(
    "body, h, now",
    [
        (BODY.replace("42", "43"), headers(), NOW),
        (BODY, headers(), NOW + 301),
        (BODY, {"webhook-id": "msg_1"}, NOW),
        (BODY, {**headers(), "webhook-timestamp": "soon"}, NOW),
    ],
)
def test_refuses_a_changed_body_an_old_timestamp_or_missing_headers(body: str, h: dict, now: int) -> None:
    with pytest.raises(WebhookVerificationError):
        verify_webhook(body, h, SECRET, now=now)


def test_refuses_another_secret() -> None:
    with pytest.raises(WebhookVerificationError):
        verify_webhook(BODY, headers(), "whsec_" + base64.b64encode(os.urandom(24)).decode(), now=NOW)


def test_reads_a_credits_low_event() -> None:
    body = json.dumps(
        {"type": "credits.low", "timestamp": "2026-10-04T12:00:00Z", "data": {"balance": 40, "threshold": 100}}
    )
    event = verify_webhook(body, headers(body), SECRET, now=NOW)
    assert event["type"] == "credits.low"
    assert event["data"]["balance"] < event["data"]["threshold"]
