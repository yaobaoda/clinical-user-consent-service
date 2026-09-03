import json

import httpx

from consent_service.infrai_captcha import InfraiCaptchaClient


def test_captcha_retry_honors_retry_after_and_keeps_request_shape() -> None:
    calls: list[httpx.Request] = []
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "1"},
                json={"ok": False, "data": None, "error": {"message": "retry later"}, "metadata": {}},
            )
        return httpx.Response(
            200,
            json={"ok": True, "data": {"verified": True}, "error": None, "metadata": {}},
        )

    client = InfraiCaptchaClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
    )
    result = client.verify("captcha-response", "consent_grant")

    assert result == {"verified": True}
    assert sleeps == [1.0]
    assert [request.method for request in calls] == ["POST", "POST"]
    assert json.loads(calls[0].content) == {
        "token": "captcha-response",
        "vendor": "auto",
        "action": "consent_grant",
    }
