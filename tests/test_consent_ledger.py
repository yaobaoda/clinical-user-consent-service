import pytest

from consent_service.consent_ledger import (
    AccountStatus,
    ConsentDecisionError,
    ConsentLedger,
)


def test_suspended_account_cannot_gain_scope_but_can_lose_one() -> None:
    ledger = ConsentLedger()
    ledger.onboard_tenant("clinic-west")
    ledger.register_account("clinic-west", "patient-42")
    ledger.grant("op-1", "clinic-west", "patient-42", "records.read")
    ledger.set_account_status("clinic-west", "patient-42", AccountStatus.SUSPENDED)

    with pytest.raises(ConsentDecisionError, match="Only active accounts"):
        ledger.grant("op-2", "clinic-west", "patient-42", "appointments.write")

    receipt = ledger.revoke("op-3", "clinic-west", "patient-42", "records.read")

    assert receipt.decision == "revoked"
    assert ledger.scopes_for("clinic-west", "patient-42") == []


def test_operation_id_makes_repeated_grant_same_decision() -> None:
    ledger = ConsentLedger()
    ledger.onboard_tenant("clinic-east")
    ledger.register_account("clinic-east", "patient-7")

    first = ledger.grant("stable-op", "clinic-east", "patient-7", "labs.read")
    repeated = ledger.grant("stable-op", "clinic-east", "patient-7", "labs.read")

    assert repeated == first
    assert ledger.scopes_for("clinic-east", "patient-7") == ["labs.read"]

    with pytest.raises(ConsentDecisionError, match="already bound"):
        ledger.revoke("stable-op", "clinic-east", "patient-7", "labs.read")
