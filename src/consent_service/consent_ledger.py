from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class AccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class ConsentDecisionError(ValueError):
    pass


@dataclass
class Account:
    tenant_id: str
    user_id: str
    status: AccountStatus = AccountStatus.ACTIVE
    scopes: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ConsentReceipt:
    operation_id: str
    tenant_id: str
    user_id: str
    scope: str
    decision: str
    recorded_at: str


class ConsentLedger:
    def __init__(self) -> None:
        self._tenants: set[str] = set()
        self._accounts: dict[tuple[str, str], Account] = {}
        self._receipts: dict[str, ConsentReceipt] = {}

    def onboard_tenant(self, tenant_id: str) -> None:
        self._tenants.add(tenant_id)

    def register_account(self, tenant_id: str, user_id: str) -> Account:
        if tenant_id not in self._tenants:
            raise ConsentDecisionError("Tenant must be onboarded first")
        account = Account(tenant_id=tenant_id, user_id=user_id)
        self._accounts[(tenant_id, user_id)] = account
        return account

    def set_account_status(
        self, tenant_id: str, user_id: str, status: AccountStatus
    ) -> Account:
        account = self._account(tenant_id, user_id)
        account.status = status
        if status == AccountStatus.CLOSED:
            account.scopes.clear()
        return account

    def grant(
        self, operation_id: str, tenant_id: str, user_id: str, scope: str
    ) -> ConsentReceipt:
        existing = self._existing_receipt(operation_id, tenant_id, user_id, scope, "granted")
        if existing:
            return existing
        account = self._account(tenant_id, user_id)
        if account.status != AccountStatus.ACTIVE:
            raise ConsentDecisionError("Only active accounts can receive consent scopes")
        account.scopes.add(scope)
        return self._record(operation_id, tenant_id, user_id, scope, "granted")

    def revoke(
        self, operation_id: str, tenant_id: str, user_id: str, scope: str
    ) -> ConsentReceipt:
        existing = self._existing_receipt(operation_id, tenant_id, user_id, scope, "revoked")
        if existing:
            return existing
        account = self._account(tenant_id, user_id)
        account.scopes.discard(scope)
        return self._record(operation_id, tenant_id, user_id, scope, "revoked")

    def scopes_for(self, tenant_id: str, user_id: str) -> list[str]:
        return sorted(self._account(tenant_id, user_id).scopes)

    def _account(self, tenant_id: str, user_id: str) -> Account:
        try:
            return self._accounts[(tenant_id, user_id)]
        except KeyError as exc:
            raise ConsentDecisionError("Account does not exist") from exc

    def _existing_receipt(
        self,
        operation_id: str,
        tenant_id: str,
        user_id: str,
        scope: str,
        decision: str,
    ) -> ConsentReceipt | None:
        existing = self._receipts.get(operation_id)
        if existing is None:
            return None
        if (
            existing.tenant_id,
            existing.user_id,
            existing.scope,
            existing.decision,
        ) != (tenant_id, user_id, scope, decision):
            raise ConsentDecisionError("Operation ID is already bound to another decision")
        return existing

    def _record(
        self,
        operation_id: str,
        tenant_id: str,
        user_id: str,
        scope: str,
        decision: str,
    ) -> ConsentReceipt:
        receipt = ConsentReceipt(
            operation_id=operation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            scope=scope,
            decision=decision,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        self._receipts[operation_id] = receipt
        return receipt
