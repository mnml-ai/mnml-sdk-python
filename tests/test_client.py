from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

import pytest

from mnml_ai import Mnml, MnmlError, MnmlTimeoutError

from .conftest import FakeApi, fail, ok

STARTED = {"id": "1", "ids": ["1"], "status": "queued", "credits_charged": 25, "replayed": False, "notes": []}


def client(api: FakeApi, slept: List[float], **kwargs: object) -> Mnml:
    return Mnml("mk_live_test", transport=api, sleep=slept.append, **kwargs)  # type: ignore[arg-type]


def test_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MNML_API_KEY", raising=False)
    with pytest.raises(ValueError, match="MNML_API_KEY"):
        Mnml()


def test_reads_the_key_from_the_environment(monkeypatch: pytest.MonkeyPatch, slept: List[float]) -> None:
    monkeypatch.setenv("MNML_API_KEY", "mk_live_env")
    api = FakeApi([ok({"id": "a"})])
    Mnml(transport=api, sleep=slept.append).account.get()
    assert api.calls[0]["headers"]["Authorization"] == "Bearer mk_live_env"


def test_sends_the_key_and_body_and_returns_data(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    started = client(api, slept).renders.create(prompt="Timber facade", image_url="https://example.com/a.png")
    assert started["credits_charged"] == 25
    call = api.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://api.mnml.ai/v1/renders"
    assert call["headers"]["Authorization"] == "Bearer mk_live_test"
    assert call["headers"]["Content-Type"] == "application/json"
    assert re.fullmatch(r"mnml-sdk-python/\d+\.\d+\.\d+", call["headers"]["User-Agent"])
    assert re.fullmatch(r"[0-9a-f-]{36}", call["headers"]["Idempotency-Key"])
    assert json.loads(call["body"]) == {"prompt": "Timber facade", "image_url": "https://example.com/a.png"}


def test_sends_no_idempotency_key_on_a_read(slept: List[float]) -> None:
    api = FakeApi([ok({"engines": [], "video_models": []})])
    client(api, slept).engines.list()
    assert "Idempotency-Key" not in api.calls[0]["headers"]


def test_retries_a_429_after_retry_after_with_the_same_key(slept: List[float]) -> None:
    api = FakeApi([fail(429, "RATE_LIMITED", {"Retry-After": "2"}), ok(STARTED, 202)])
    client(api, slept).edits.create(job_id="3", prompt="Dark brick")
    assert slept == [2.0]
    keys = [c["headers"]["Idempotency-Key"] for c in api.calls]
    assert len(keys) == 2 and keys[0] == keys[1]


def test_keeps_a_key_you_pass(slept: List[float]) -> None:
    api = FakeApi([fail(500, "INTERNAL"), ok(STARTED, 202)])
    client(api, slept).renders.create(prompt="x", idempotency_key="order-42")
    assert [c["headers"]["Idempotency-Key"] for c in api.calls] == ["order-42", "order-42"]


def test_hands_back_a_long_retry_after_instead_of_sleeping(slept: List[float]) -> None:
    api = FakeApi([fail(429, "RATE_LIMITED", {"Retry-After": "3600"})])
    with pytest.raises(MnmlError) as caught:
        client(api, slept).account.get()
    assert caught.value.code == "RATE_LIMITED"
    assert slept == [] and len(api.calls) == 1


def test_retries_a_dropped_connection(slept: List[float]) -> None:
    api = FakeApi([ConnectionResetError("reset"), ok({"id": "a"})])
    assert client(api, slept).account.get()["id"] == "a"
    assert len(api.calls) == 2 and len(slept) == 1


def test_gives_up_after_max_retries(slept: List[float]) -> None:
    api = FakeApi([fail(503, "SERVICE_UNAVAILABLE"), fail(503, "SERVICE_UNAVAILABLE")])
    with pytest.raises(MnmlError) as caught:
        client(api, slept, max_retries=1).account.get()
    assert caught.value.status == 503
    assert len(api.calls) == 2


def test_raises_the_api_error_with_code_request_id_and_issues(slept: List[float]) -> None:
    issues = [{"path": "prompt", "message": "Required"}]
    api = FakeApi([fail(400, "VALIDATION_FAILED", issues=issues)])
    with pytest.raises(MnmlError) as caught:
        client(api, slept).renders.create(prompt="")
    err = caught.value
    assert (err.code, err.status, err.request_id) == ("VALIDATION_FAILED", 400, "req_1")
    assert err.issues == issues
    assert "VALIDATION_FAILED" in repr(err)


def test_waits_for_a_job_to_settle(slept: List[float]) -> None:
    job = lambda status: ok({"id": "9", "status": status, "outputs": []})  # noqa: E731
    api = FakeApi([job("queued"), job("processing"), job("succeeded")])
    done = client(api, slept).jobs.wait("9", interval=1.0)
    assert done["status"] == "succeeded"
    assert slept == [1.0, 1.0]
    assert all(c["url"].endswith("/v1/jobs/9") for c in api.calls)


def test_stops_waiting_at_the_deadline(slept: List[float]) -> None:
    api = FakeApi([ok({"id": "9", "status": "processing", "outputs": []})])
    with pytest.raises(MnmlTimeoutError) as caught:
        client(api, slept).jobs.wait("9", interval=5.0, timeout=1.0)
    assert caught.value.job_id == "9"


def test_cancels_a_job_and_escapes_its_id(slept: List[float]) -> None:
    api = FakeApi([ok({"id": "a/b", "outcome": "refunded", "credits_refunded": 25})])
    client(api, slept).jobs.cancel("a/b")
    assert api.calls[0]["url"] == "https://api.mnml.ai/v1/jobs/a%2Fb/cancel"


def test_uploads_bytes_as_multipart(slept: List[float]) -> None:
    api = FakeApi([ok({"id": "u1"}, 201)])
    client(api, slept, base_url="https://api.example.com/").uploads.create(b"\x89PNG", filename="a.png", purpose="mask")
    call = api.calls[0]
    assert call["url"] == "https://api.example.com/v1/uploads"
    assert call["headers"]["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'filename="a.png"' in call["body"] and b"\x89PNG" in call["body"]
    assert b'name="purpose"\r\n\r\nmask' in call["body"]


def test_uploads_a_path_under_its_own_name(tmp_path: Path, slept: List[float]) -> None:
    image = tmp_path / "massing.png"
    image.write_bytes(b"png-bytes")
    api = FakeApi([ok({"id": "u1"}, 201)])
    client(api, slept).uploads.create(image)
    assert b'filename="massing.png"' in api.calls[0]["body"]


def test_uploads_a_url_as_json(slept: List[float]) -> None:
    api = FakeApi([ok({"id": "u1"}, 201)])
    client(api, slept).uploads.create(url="https://example.com/a.png")
    assert json.loads(api.calls[0]["body"]) == {"url": "https://example.com/a.png"}


def test_upload_needs_a_file_or_a_url(slept: List[float]) -> None:
    with pytest.raises(ValueError):
        client(FakeApi([]), slept).uploads.create()
