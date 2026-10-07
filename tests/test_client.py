from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

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


def test_sends_only_the_fields_you_set(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).edits.create(job_id="3", kind="erase", region={"polygon": [(0.1, 0.1), (0.5, 0.1), (0.3, 0.4)]})
    assert json.loads(api.calls[0]["body"]) == {
        "job_id": "3",
        "kind": "erase",
        "region": {"polygon": [[0.1, 0.1], [0.5, 0.1], [0.3, 0.4]]},
    }


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"\0" * 8
WEBP = b"RIFF\0\0\0\0WEBPVP8 "


def data_uri(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def test_sends_image_bytes_as_a_data_uri(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).renders.create(prompt="x", image=JPEG)
    assert json.loads(api.calls[0]["body"]) == {"prompt": "x", "image": data_uri("image/jpeg", JPEG)}
    assert api.calls[0]["headers"]["Content-Type"] == "application/json"


def test_reads_an_image_path_into_a_data_uri(tmp_path: Path, slept: List[float]) -> None:
    image = tmp_path / "house.webp"
    image.write_bytes(WEBP)
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).enhancements.create(kind="upscale", image=image)
    assert json.loads(api.calls[0]["body"])["image"] == data_uri("image/webp", WEBP)


def test_reads_an_open_file_and_marks_unknown_bytes_as_octet_stream(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).renders.create(prompt="x", image=io.BytesIO(b"not an image"))
    assert json.loads(api.calls[0]["body"])["image"] == data_uri("application/octet-stream", b"not an image")


def test_sends_an_image_string_unchanged(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202), ok(STARTED, 202)])
    mnml = client(api, slept)
    mnml.renders.create(prompt="x", image="https://example.com/a.png")
    # A str is never read as a path, even when it looks like one.
    mnml.renders.create(prompt="x", image="house.jpg")
    assert [json.loads(c["body"])["image"] for c in api.calls] == ["https://example.com/a.png", "house.jpg"]


def test_encodes_each_reference(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).renders.create(
        prompt="x",
        references=["https://example.com/style.png", PNG, {"image": JPEG, "mode": "material"}, {"job_id": "7"}],
    )
    assert json.loads(api.calls[0]["body"])["references"] == [
        "https://example.com/style.png",
        data_uri("image/png", PNG),
        {"image": data_uri("image/jpeg", JPEG), "mode": "material"},
        {"job_id": "7"},
    ]


def test_sends_a_mask_as_a_data_uri(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202)])
    client(api, slept).edits.create(image="https://example.com/a.png", mask=PNG, prompt="A red door")
    assert json.loads(api.calls[0]["body"]) == {
        "image": "https://example.com/a.png",
        "mask": data_uri("image/png", PNG),
        "prompt": "A red door",
    }


def test_sends_an_end_frame_as_a_data_uri(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202), ok(STARTED, 202)])
    mnml = client(api, slept)
    mnml.videos.create(job_id="3", end_frame=JPEG)
    mnml.videos.create(job_id="3", end_frame={"image": bytearray(JPEG)})
    assert json.loads(api.calls[0]["body"])["end_frame"] == data_uri("image/jpeg", JPEG)
    assert json.loads(api.calls[1]["body"])["end_frame"] == {"image": data_uri("image/jpeg", JPEG)}


def test_create_and_wait_reads_a_file_once(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202), ok({"id": "1", "status": "succeeded", "outputs": []})])
    client(api, slept).edits.create_and_wait(image=io.BytesIO(PNG), prompt="x")
    assert json.loads(api.calls[0]["body"])["image"] == data_uri("image/png", PNG)


def test_asks_the_api_to_hold_a_render_and_polls_nothing_when_it_comes_back_settled(slept: List[float]) -> None:
    done = {"id": "7", "status": "succeeded", "outputs": [{"url": "u", "media": "image"}]}
    api = FakeApi([ok({**STARTED, "id": "7", "ids": ["7"], "jobs": [done]}), ok({**STARTED, "ids": ["8"]}, 202)])
    mnml = client(api, slept)
    assert mnml.renders.create_and_wait(prompt="x") == [done]
    assert len(api.calls) == 1
    assert api.calls[0]["url"] == "https://api.mnml.ai/v1/renders?wait=50"
    assert api.calls[0]["timeout"] == 60.0 + 50
    mnml.renders.create(prompt="x", wait=30)
    assert api.calls[1]["url"] == "https://api.mnml.ai/v1/renders?wait=30"
    assert json.loads(api.calls[1]["body"]) == {"prompt": "x"}


def test_refuses_a_field_the_api_does_not_take(slept: List[float]) -> None:
    with pytest.raises(TypeError):
        client(FakeApi([]), slept).renders.create(prompt="x", colour="red")  # type: ignore[call-arg]


def test_starts_a_render_and_waits_for_every_job_its_count_started(slept: List[float]) -> None:
    job = lambda job_id, status: ok({"id": job_id, "status": status, "outputs": []})  # noqa: E731
    api = FakeApi(
        [
            ok({**STARTED, "ids": ["1", "2"]}, 202),
            job("1", "processing"),
            job("2", "succeeded"),
            job("1", "succeeded"),
        ]
    )
    jobs = client(api, slept).renders.create_and_wait(prompt="x", count=2, idempotency_key="brief-1", interval=1.0)
    assert [(j["id"], j["status"]) for j in jobs] == [("1", "succeeded"), ("2", "succeeded")]
    assert api.calls[0]["headers"]["Idempotency-Key"] == "brief-1"
    assert json.loads(api.calls[0]["body"]) == {"prompt": "x", "count": 2}
    # Job 2 settled on the first round, so the second round reads only job 1.
    assert [c["url"].rsplit("/", 1)[1] for c in api.calls[1:]] == ["1", "2", "1"]
    assert slept == [1.0]


def test_waits_for_a_video_at_its_own_pace(slept: List[float]) -> None:
    api = FakeApi([ok(STARTED, 202), ok({"id": "1", "status": "processing"}), ok({"id": "1", "status": "succeeded"})])
    done = client(api, slept).videos.create_and_wait(job_id="3", camera_movement="dolly-in,tilt-up")
    assert done["status"] == "succeeded"
    assert slept == [10.0]


class FileApi:
    """A transport that serves one file, or one refusal."""

    def __init__(self, status: int, body: bytes, headers: Dict[str, str]) -> None:
        self.answer = (status, headers, body)
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout: float
    ) -> Tuple[int, Mapping[str, str], bytes]:
        self.calls.append({"method": method, "url": url, "headers": dict(headers)})
        return self.answer


def test_downloads_an_output_without_sending_the_key(tmp_path: Path, slept: List[float]) -> None:
    api = FileApi(200, b"\x89PNG", {"Content-Type": "image/png"})
    url = "https://api.mnml.ai/v1/files/9?exp=1&sig=abc"
    target = tmp_path / "render.png"
    file = client(api, slept).files.download({"url": url, "media": "image", "expires_at": "x"}, to=target)  # type: ignore[arg-type]
    assert file == {"data": b"\x89PNG", "content_type": "image/png"}
    assert target.read_bytes() == b"\x89PNG"
    assert api.calls[0]["url"] == url
    assert "Authorization" not in api.calls[0]["headers"]


def test_raises_not_found_for_an_expired_output_link(slept: List[float]) -> None:
    refusal = json.dumps({"success": False, "error": {"code": "NOT_FOUND", "message": "expired"}}).encode()
    api = FileApi(404, refusal, {"X-Request-Id": "req_9"})
    with pytest.raises(MnmlError) as caught:
        client(api, slept).files.download("https://api.mnml.ai/v1/files/9?exp=1&sig=x")
    assert (caught.value.code, caught.value.status, caught.value.request_id) == ("NOT_FOUND", 404, "req_9")
