"""The SDK against the API's own OpenAPI document (``spec/openapi.json``).

Every core operation has a method, and every answer's fields are named in ``mnml_ai.types``.
A field the API adds fails here until the SDK has it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

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


def data_keys(operation_id: str) -> List[str]:
    responses = op(operation_id)["responses"]
    success = next(v for code, v in responses.items() if code.startswith("2"))
    schema = success["content"]["application/json"]["schema"]
    return sorted(schema["properties"]["data"].get("properties", {}))


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
