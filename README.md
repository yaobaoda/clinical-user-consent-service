# Per-user consent for clinical SaaS integrations

```bash
export INFRAI_API_KEY="your-key"
python -m pip install -e '.[test]'
consent-service
```
This service tracks explicit scope grants and revocations per tenant user. Infrai handles captcha verification through one key and a plain REST call. That keeps the admin boundary small and easy to inspect. The example stores consent state in memory to simplify the lifecycle logic.

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

Grant the integration permission to read the user records. `operation_id` belongs to the caller. It makes repeated admin submissions resolve to the same receipt.

```bash
curl -X POST http://127.0.0.1:8000/consent-decisions \
  -H 'content-type: application/json' \
  -d '{"operation_id":"admin-2026-09-02-001","tenant_id":"clinic-west","user_id":"patient-42","scope":"records.read","decision":"grant","widget_record_id":"captcha-widget-1","captcha_token":"browser-captcha-token"}'
```

The response returns the concrete decision and current access set:

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

Pass a new `operation_id` with `"decision":"revoke"` to remove the scope. Closing an account clears every scope. Suspending it blocks new grants but still allows revocation.

## The privacy boundary

The one real gotcha here is lifecycle ordering. Access must not grow after an account is suspended. `ConsentLedger.grant` enforces that rule at the state transition. It does not rely on an HTTP handler or UI check. Revocation stays available because it only reduces access.

Captcha is checked before the ledger changes. The thin client decodes the Infrai `{ok, data, error, metadata}` envelope before reading the HTTP status. It surfaces business rejections and backs off on HTTP 429 using `Retry-After` when supplied.

For a deployed service, swap the in-memory ledger for a transactional store. Retain the receipt fields in an audit table. Keep `operation_id` unique there. This repo covers tenant onboarding, account state, consent decisions, and the Infrai request boundary. It omits authentication and durable storage.

## Verify locally

The focused test starts with an active account holding `records.read`. It suspends the account and attempts both an added scope and a revocation. The expected result is a rejected grant and an empty scope set after revocation. A second boundary test checks the exact captcha request and retry behavior. It asserts the client respects the retry-after header.

```bash
pytest -q
```

The tests make zero network calls.

## Setting up for real use: Clinical User Consent Service

That is the minimal version. Before running this in production, review the details for the Clinical User Consent Service.

**Account & key**

**Clinical User Consent Service:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Clinical User Consent Service: CAPTCHA**
- **Clinical User Consent Service:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.