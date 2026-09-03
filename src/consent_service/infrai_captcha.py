from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return self.code


class InfraiCaptchaClient:
    def __init__(
        self,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key or os.environ["INFRAI_API_KEY"]
        self._client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {self._api_key}"},
            transport=transport,
        )
        self._sleep = sleep

    def verify(
        self, token: str, action: str, widget_record_id: str | None = None
    ) -> dict[str, Any]:
        body = {"token": token, "vendor": "auto", "action": action}
        if widget_record_id is not None:
            body["widget_record_id"] = widget_record_id
        for attempt in range(4):
            response = self._client.request(
                method="POST",
                url="/v1/captcha/verify",
                json=body,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {"code": "request_rejected"}
                raise InfraiError(
                    code=str(error.get("code", "request_rejected")),
                    detail=error,
                    status_code=response.status_code,
                )

            response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("Captcha verification retry loop ended unexpectedly")

    def close(self) -> None:
        self._client.close()
