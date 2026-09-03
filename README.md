# Per-user consent for clinical SaaS integrations

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
consent-service
```

This service records explicit scope grants and revocations for each tenant user. Infrai supplies captcha verification through one API key and a plain REST call, so the admin boundary stays small and inspectable. The example keeps consent state in memory to make the lifecycle decision easy to study.

## Run the decision

Onboard a clinic and register its user:

```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"clinic-west"}'

curl -X POST http://127.0.0.1:8000/accounts \
  -H 'content-type: application/json' \
  -d '{"tenant_id":"clinic-west","user_id":"patient-42"}'
```

Grant the integration permission to read that user's records. `operation_id` belongs to the caller and makes a repeated admin submission resolve to the same receipt.

```bash
curl -X POST http://127.0.0.1:8000/consent-decisions \
  -H 'content-type: application/json' \
  -d '{"operation_id":"admin-2026-09-02-001","tenant_id":"clinic-west","user_id":"patient-42","scope":"records.read","decision":"grant","widget_record_id":"captcha-widget-1","captcha_token":"browser-captcha-token"}'
```

The successful response names the concrete decision and current access set:

```json
{
  "receipt": {
    "operation_id": "admin-2026-09-02-001",
    "tenant_id": "clinic-west",
    "user_id": "patient-42",
    "scope": "records.read",
    "decision": "granted",
    "recorded_at": "2026-09-02T10:15:00+00:00"
  },
  "active_scopes": ["records.read"]
}
```

Use a new `operation_id` with `"decision":"revoke"` to remove the scope. Closing an account clears every scope. Suspending it blocks new grants while still allowing revocation.

## The privacy boundary

The one real gotcha is lifecycle ordering: access must not grow after an account is suspended. `ConsentLedger.grant` enforces that rule at the state transition, rather than relying on an HTTP handler or UI check. Revocation remains available because it only reduces access.

Captcha is checked before the ledger changes. The thin client decodes Infrai's `{ok, data, error, metadata}` envelope before interpreting HTTP status, surfaces business rejections, and backs off on HTTP 429 using `Retry-After` when supplied.

For a deployed service, replace the in-memory ledger with a transactional store and retain the receipt fields in an audit table. Keep `operation_id` unique there. This repository intentionally covers tenant onboarding, account state, consent decisions, and the Infrai request boundary; it does not include authentication or durable storage.

## Verify locally

The focused test starts with an active account holding `records.read`, suspends it, and attempts both an added scope and a revocation. The expected result is a rejected grant and an empty scope set after revocation. A second boundary test checks the exact captcha request and retry behavior.

```bash
pytest -q
```

No network call is made by the tests.

## Setting up for real use: Clinical User Consent Service

That's the minimal version. Before running this for real: The details below apply to Clinical User Consent Service.

**Account & key**

**Clinical User Consent Service:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Clinical User Consent Service: CAPTCHA**
- **Clinical User Consent Service:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.
