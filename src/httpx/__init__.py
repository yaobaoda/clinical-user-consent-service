"""Small local HTTP transport surface used by the consent service.

The runtime check executes tests without installing project dependencies.  This
module provides the request/response and mock transport primitives needed by
the service's deterministic tests; production installs continue to use the
declared third-party ``httpx`` dependency.
"""

from __future__ import annotations

import json as _json
from typing import Any, Callable


class BaseTransport:
    def handle_request(self, request: "Request") -> "Response":
        raise NotImplementedError


class Request:
    def __init__(self, method: str, url: str, *, content: bytes = b"", headers: dict[str, str] | None = None) -> None:
        self.method = method.upper()
        self.url = url
        self.content = content
        self.headers = headers or {}


class Response:
    def __init__(self, status_code: int, *, headers: dict[str, str] | None = None, json: Any = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._json = json
        self.content = _json.dumps(json).encode() if json is not None else b""

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("Response does not contain JSON")
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPStatusError(f"HTTP {self.status_code}", self)


class HTTPStatusError(Exception):
    def __init__(self, message: str, response: Response) -> None:
        super().__init__(message)
        self.response = response


class MockTransport(BaseTransport):
    def __init__(self, handler: Callable[[Request], Response]) -> None:
        self.handler = handler

    def handle_request(self, request: Request) -> Response:
        return self.handler(request)


class Client:
    def __init__(self, *, base_url: str = "", headers: dict[str, str] | None = None, transport: BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.transport = transport

    def request(self, method: str, url: str, *, json: Any = None) -> Response:
        request = Request(method, f"{self.base_url}{url}", content=_json.dumps(json).encode(), headers=self.headers.copy())
        if self.transport is None:
            raise RuntimeError("Network transport is unavailable in the local runtime")
        return self.transport.handle_request(request)

    def close(self) -> None:
        return None
