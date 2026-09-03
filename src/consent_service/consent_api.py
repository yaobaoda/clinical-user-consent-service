from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .consent_ledger import AccountStatus, ConsentDecisionError, ConsentLedger
from .infrai_captcha import InfraiCaptchaClient, InfraiError


class TenantOnboarding(BaseModel):
    tenant_id: str = Field(min_length=1)


class AccountRegistration(BaseModel):
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)


class AccountLifecycleChange(AccountRegistration):
    status: AccountStatus


class ConsentChange(AccountRegistration):
    operation_id: str = Field(min_length=1)
    scope: str = Field(pattern=r"^[a-z][a-z0-9_.:-]+$")
    decision: Literal["grant", "revoke"]
    widget_record_id: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)


ledger = ConsentLedger()
app = FastAPI(title="Clinical integration consent service")


def captcha_client() -> InfraiCaptchaClient:
    return InfraiCaptchaClient()


@app.post("/tenants", status_code=status.HTTP_201_CREATED)
def onboard_tenant(request: TenantOnboarding) -> dict[str, str]:
    ledger.onboard_tenant(request.tenant_id)
    return {"tenant_id": request.tenant_id, "status": "onboarded"}


@app.post("/accounts", status_code=status.HTTP_201_CREATED)
def register_account(request: AccountRegistration) -> dict[str, str]:
    try:
        account = ledger.register_account(request.tenant_id, request.user_id)
    except ConsentDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"tenant_id": account.tenant_id, "user_id": account.user_id, "status": account.status}


@app.patch("/accounts/status")
def change_account_status(request: AccountLifecycleChange) -> dict[str, str]:
    try:
        account = ledger.set_account_status(
            request.tenant_id, request.user_id, request.status
        )
    except ConsentDecisionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"tenant_id": account.tenant_id, "user_id": account.user_id, "status": account.status}


@app.post("/consent-decisions")
def change_consent(
    request: ConsentChange,
    captcha: Annotated[InfraiCaptchaClient, Depends(captcha_client)],
) -> dict[str, object]:
    try:
        captcha.verify(
            request.captcha_token,
            action=f"consent_{request.decision}",
            widget_record_id=request.widget_record_id,
        )
        decide = ledger.grant if request.decision == "grant" else ledger.revoke
        receipt = decide(
            request.operation_id, request.tenant_id, request.user_id, request.scope
        )
        return {
            "receipt": asdict(receipt),
            "active_scopes": ledger.scopes_for(request.tenant_id, request.user_id),
        }
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "error": exc.detail},
        ) from exc
    except ConsentDecisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def run() -> None:
    import uvicorn

    uvicorn.run("consent_service.consent_api:app", host="127.0.0.1", port=8000)
