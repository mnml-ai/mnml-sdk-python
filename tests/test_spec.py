"""The SDK against the API's own OpenAPI document (``spec/openapi.json``).

Every core operation has a method, every request field is a keyword argument, every answer's
fields are named in ``mnml_ai.types``, and every value the API lists is in its ``Literal``.
A field or value the API adds fails here until the SDK has it.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, get_args, get_type_hints

from mnml_ai import Mnml
from mnml_ai import types as t

SPEC: Dict[str, Any] = json.loads((Path(__file__).parent.parent / "spec" / "openapi.json").read_text())
OPS = [op for path in SPEC["paths"].values() for op in path.values()]

#: operationId -> the client method that calls it.
COVERED = {
    "getAccount": "account.get",
    "listEngines": "engines.list",
    "createUpload": "uploads.create",
    "createRender": "renders.create",
    "createEdit": "edits.create",
    "createEnhancement": "enhancements.create",
    "createVideo": "videos.create",
    "getJob": "jobs.get",
    "cancelJob": "jobs.cancel",
}
#: Not client calls: the document itself, and the signed output link a job hands back.
NOT_CALLS = {"getOpenApi", "getJobFile"}


def op(operation_id: str) -> Dict[str, Any]:
    return next(o for o in OPS if o["operationId"] == operation_id)


def data(operation_id: str) -> Dict[str, Any]:
    responses = op(operation_id)["responses"]
    success = next(v for code, v in responses.items() if code.startswith("2"))
    schema: Dict[str, Any] = success["content"]["application/json"]["schema"]["properties"]["data"]
    return schema


def data_keys(operation_id: str) -> List[str]:
    return keys_of(data(operation_id))


def body(operation_id: str) -> Dict[str, Any]:
    schema: Dict[str, Any] = op(operation_id)["requestBody"]["content"]["application/json"]["schema"]
    return schema


def object_of(schema: Dict[str, Any]) -> Dict[str, Any]:
    """A schema's object, through an array and an ``anyOf`` (nullable, or an image string or object)."""
    schema = schema.get("items", schema)
    return next((m for m in schema.get("anyOf", []) if "properties" in m), schema)


def keys_of(schema: Dict[str, Any]) -> List[str]:
    """A schema's keys, through an array and an ``anyOf``."""
    return sorted(object_of(schema).get("properties", {}))


def enum_of(schema: Dict[str, Any]) -> List[str]:
    return sorted(schema["enum"])


def literal(alias: Any) -> List[str]:
    return sorted(get_args(alias))


def fields_of(method: Callable[..., Any]) -> List[str]:
    """A create method's request fields: its keyword arguments, less the client's own."""
    own = {"self", "idempotency_key", "interval", "timeout", "wait"}
    return sorted(p for p in inspect.signature(method).parameters if p not in own)


def test_has_a_method_for_every_core_operation() -> None:
    core = sorted(o["operationId"] for o in OPS if not o.get("x-mnml-legacy") and o["operationId"] not in NOT_CALLS)
    assert core == sorted(COVERED)
    client = Mnml("mk_test")
    for dotted in COVERED.values():
        resource, method = dotted.split(".")
        assert callable(getattr(getattr(client, resource), method)), dotted


def test_names_every_answer_field() -> None:
    assert sorted(t.RenderStarted.__annotations__) == data_keys("createRender")
    for operation_id in ("createEdit", "createEnhancement", "createVideo"):
        assert sorted(t.JobStarted.__annotations__) == data_keys(operation_id)
    assert sorted(t.Job.__annotations__) == data_keys("getJob")
    assert sorted(t.JobCanceled.__annotations__) == data_keys("cancelJob")
    assert sorted(t.Upload.__annotations__) == data_keys("createUpload")
    assert sorted(t.Account.__annotations__) == data_keys("getAccount")


def test_takes_every_request_field_as_a_keyword() -> None:
    client = Mnml("mk_test")
    for operation_id, resource in (
        ("createRender", client.renders),
        ("createEdit", client.edits),
        ("createEnhancement", client.enhancements),
        ("createVideo", client.videos),
    ):
        expected = keys_of(body(operation_id))
        assert fields_of(resource.create) == expected, operation_id
        assert fields_of(resource.create_and_wait) == expected, operation_id
    required = set(body("createRender")["required"])
    params = inspect.signature(client.renders.create).parameters
    assert {p for p, v in params.items() if v.default is inspect.Parameter.empty and p != "self"} == required


def test_names_the_nested_answers_and_request_parts() -> None:
    account = data("getAccount")["properties"]
    assert sorted(t.AccountKey.__annotations__) == keys_of(account["key"])
    assert sorted(t.AccountLimits.__annotations__) == keys_of(account["limits"])
    assert sorted(t.AccountCredits.__annotations__) == keys_of(account["credits"])
    engines = data("listEngines")["properties"]
    engine = engines["engines"]["items"]["properties"]
    assert sorted(t.Engines.__annotations__) == data_keys("listEngines")
    assert sorted(t.Engine.__annotations__) == keys_of(engines["engines"])
    assert sorted(t.EnginePrices.__annotations__) == keys_of(engine["prices"])
    assert sorted(t.EngineCapabilities.__annotations__) == keys_of(engine["capabilities"])
    video = engines["video_models"]
    assert sorted(t.VideoModel.__annotations__) == keys_of(video)
    assert sorted(t.VideoPrice.__annotations__) == keys_of(video["items"]["properties"]["prices"])
    job = data("getJob")["properties"]
    assert sorted(t.JobOutput.__annotations__) == keys_of(job["outputs"])
    assert sorted(t.JobError.__annotations__) == keys_of(job["error"])
    render = body("createRender")["properties"]
    assert sorted(t.Reference.__annotations__) == keys_of(render["references"])
    region = body("createEdit")["properties"]["region"]["properties"]
    assert sorted(t.Region.__annotations__) == sorted(region)
    assert sorted(t.Box.__annotations__) == sorted(region["box"]["properties"])
    assert sorted(t.Frame.__annotations__) == keys_of(body("createVideo")["properties"]["end_frame"])


def test_names_every_value_the_api_lists() -> None:
    render = body("createRender")["properties"]
    assert literal(t.Mode) == enum_of(render["mode"])
    assert literal(t.AspectRatio) == enum_of(render["aspect_ratio"])
    assert literal(t.ReferenceMode) == enum_of(object_of(render["references"])["properties"]["mode"])
    enhancement = body("createEnhancement")["properties"]
    assert literal(t.EnhancementKind) == enum_of(enhancement["kind"])
    assert literal(t.OutpaintAspectRatio) == enum_of(enhancement["aspect_ratio"])
    assert literal(t.EditKind) == enum_of(body("createEdit")["properties"]["kind"])
    job = get_type_hints(t.Job)
    status = data("getJob")["properties"]["status"]
    assert literal(job["status"]) == enum_of(status)
    error = next(m for m in data("getJob")["properties"]["error"]["anyOf"] if "properties" in m)
    assert literal(get_type_hints(t.JobError)["code"]) == enum_of(error["properties"]["code"])
    outcome = data("cancelJob")["properties"]["outcome"]
    assert literal(get_type_hints(t.JobCanceled)["outcome"]) == enum_of(outcome)
    assert literal(t.UploadPurpose) == enum_of(data("createUpload")["properties"]["purpose"])


def test_takes_an_image_as_a_string_or_an_object_where_the_api_does() -> None:
    for operation_id in ("createRender", "createEdit", "createEnhancement", "createVideo"):
        assert body(operation_id)["properties"]["image"]["type"] == "string", operation_id
    assert body("createEdit")["properties"]["mask"]["type"] == "string"
    for schema in (
        body("createRender")["properties"]["references"]["items"],
        body("createVideo")["properties"]["end_frame"],
    ):
        assert sorted(m["type"] for m in schema["anyOf"]) == ["object", "string"]
