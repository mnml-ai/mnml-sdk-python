from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import pytest


class FakeApi:
    """A transport that answers from a list and records every call."""

    def __init__(self, answers: List[Union[Tuple[int, Dict[str, Any], Dict[str, str]], Exception]]) -> None:
        self.answers = list(answers)
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], body: Optional[bytes], timeout: float
    ) -> Tuple[int, Mapping[str, str], bytes]:
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body, "timeout": timeout})
        if not self.answers:
            raise AssertionError("no more answers")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        status, payload, res_headers = answer
        return status, {"X-Request-Id": "req_1", **res_headers}, json.dumps(payload).encode()


def ok(
    data: Any, status: int = 200, headers: Optional[Dict[str, str]] = None
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    return status, {"success": True, "data": data}, headers or {}


def fail(
    status: int, code: str, headers: Optional[Dict[str, str]] = None, **extra: Any
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    return status, {"success": False, "error": {"code": code, "message": f"{code} happened", **extra}}, headers or {}


@pytest.fixture
def slept() -> List[float]:
    return []
