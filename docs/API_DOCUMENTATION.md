{"t":"2026-11-07 12:26:18,242","level":"INFO","logger":"httpx2","msg":"HTTP Request: GET http://testserver/openapi.json "HTTP/1.1 200 OK""}
# API documentation

Generated from the running service's OpenAPI schema. The live, interactive version
is at **http://127.0.0.1:8000/docs** when the API is running.

## Conventions

**Authentication.** Every `/api/*` endpoint except `/api/auth/login`,
`/api/auth/register` and `/api/auth/demo-accounts` requires:

```
Authorization: Bearer <token>
X-Business-Id: <business id>
```

The business id is validated against the caller's **membership**. A business the
caller has no membership in returns `403`, not an empty result.

**Point in time.** Every read endpoint accepts `?as_of=YYYY-MM-DD`. This is a
first-class feature, not a test hook: forecast accuracy is only measurable because
any past date can be evaluated as it actually looked.

**Money.** Every monetary value is returned as an object, never a bare number:

```json
{ "paise": 82400000, "rupees": 824000.0, "display": "₹8,24,000", "compact": "₹8.24 L" }
```

`paise` is authoritative. The rest are conveniences so the interface never does
currency arithmetic.

**State labelling.** Every response that carries a financial figure also carries the
state it came from — `actual`, `predicted` or `simulated`.

**Long-horizon cross-check.** Scenario endpoints return a `long_horizon` object for
any scenario that changes the sales run-rate (`revenue_shock`, `cost_increase`,
`hiring`, `equipment_purchase`, `composite`). It re-runs the same comparison over 26
weeks, because a 13-week window sees the purchases a revenue change causes before
the collections they fund. For scenarios that only move money already owed — a
payment delay, a customer default — the field is `null` rather than a pointless
second simulation.

**Errors.**

| Code | Meaning |
|---|---|
| `401` | Missing, invalid or expired token |
| `403` | Authenticated, but no membership or insufficient role |
| `404` | Not found inside this tenant |
| `409` | Conflict — e.g. comparing a scenario that has never been run |
| `410` | Gone — a revoked or expired shared report |
| `422` | Validation failed, or a scenario could not be built |
| `429` | Rate limited |
| `500` | Internal error; the body carries the request id |

**Headers.** Every response carries `X-Request-Id` and `X-Response-Time-Ms`.

---

## Meta

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/meta` | Meta |
| `GET` | `/health` | Health |

## Authentication

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/auth/demo-accounts` | Published so the demo is reproducible. Demo credentials only. |
| `POST` | `/api/auth/login` | Login |
| `GET` | `/api/auth/me` | Me |
| `POST` | `/api/auth/register` | Register |

## Dashboard, briefing and settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/accountant/portfolio` | Multi-business view for a CA. Exception-based, not a wall of numbers. |
| `GET` | `/api/briefing` | Today's financial briefing. |
| `GET` | `/api/business` | Get Business |
| `PATCH` | `/api/business` | Update Business |
| `GET` | `/api/demo/scenarios` | Demo Scenarios |
| `POST` | `/api/demo/switch` | Regenerate the demo workspace under a different scenario. |
| `GET` | `/api/overview` | Everything the landing dashboard needs, in one round trip. |

## Ledger: transactions, invoices, counterparties, compliance

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/accounts` | Accounts |
| `GET` | `/api/compliance` | Compliance |
| `GET` | `/api/customers` | Customers |
| `GET` | `/api/customers/{cp_id}` | Customer Detail |
| `GET` | `/api/invoices` | List Invoices |
| `GET` | `/api/invoices/{invoice_id}` | Get Invoice |
| `GET` | `/api/payables` | Payables |
| `GET` | `/api/receivables` | Receivables |
| `GET` | `/api/suppliers` | Suppliers |
| `GET` | `/api/transactions` | List Transactions |
| `GET` | `/api/transactions/{txn_id}` | Get Transaction |
| `PATCH` | `/api/transactions/{txn_id}` | Patch Transaction |

## Three states, forecasting, risk, health, twin

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/alerts/{alert_id}/acknowledge` | Ack Alert |
| `GET` | `/api/forecast` | Forecast |
| `GET` | `/api/health` | Health |
| `GET` | `/api/recommendations` | Recommendations |
| `POST` | `/api/recommendations/{code}/status` | Set Rec Status |
| `GET` | `/api/risk` | Risk |
| `GET` | `/api/states/actual` | State Actual |
| `POST` | `/api/states/compare` | State Compare |
| `GET` | `/api/states/history` | State History |
| `GET` | `/api/states/predicted` | State Predicted |
| `GET` | `/api/states/reconcile` | State Reconcile |
| `GET` | `/api/twin/activity` | Twin Activity |
| `GET` | `/api/twin/graph` | Twin Graph |
| `POST` | `/api/twin/refresh` | Twin Refresh |
| `GET` | `/api/twin/state` | Twin State |
| `GET` | `/api/twin/timeline` | Twin Timeline |

## Scenario Lab

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/scenarios` | List Scenarios |
| `POST` | `/api/scenarios` | Create Scenario |
| `GET` | `/api/scenarios/catalogue` | Catalogue |
| `POST` | `/api/scenarios/compare` | Compare |
| `POST` | `/api/scenarios/optimise` | Rank several candidate decisions on a risk-adjusted objective. |
| `POST` | `/api/scenarios/quick-run` | Run a scenario without saving it - the Scenario Lab slider path. |
| `GET` | `/api/scenarios/{scenario_id}` | Get Scenario |
| `DELETE` | `/api/scenarios/{scenario_id}` | Delete Scenario |
| `POST` | `/api/scenarios/{scenario_id}/decision` | Record what the owner actually decided. |
| `GET` | `/api/scenarios/{scenario_id}/evaluate` | Compare an implemented decision against what actually happened. |
| `POST` | `/api/scenarios/{scenario_id}/run` | Run Scenario Endpoint |

## AI copilot

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/copilot/ask` | Copilot Ask |
| `GET` | `/api/copilot/history` | History |
| `GET` | `/api/copilot/suggestions` | Suggestions |
| `GET` | `/api/copilot/tools` | Tool Schema |

## Integrations and import

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/integrations` | List Integrations |
| `GET` | `/api/integrations/accounts` | Importable Accounts |
| `GET` | `/api/integrations/batches` | Batches |
| `POST` | `/api/integrations/import` | Do Import |
| `GET` | `/api/integrations/sample/{adapter}` | A ready-made sample so the import flow can be demonstrated immediately. |

## Reports and sharing

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/reports/passport` | Passport |
| `POST` | `/api/reports/passport/share` | Issue a shareable link under an explicit, revocable consent. |
| `GET` | `/api/reports/shared` | List Shared |
| `POST` | `/api/reports/shared/{report_id}/revoke` | Revoke Share |

## Public (consented, unauthenticated)

| Method | Path | Description |
|---|---|---|
| `GET` | `/public/shared/{token}` | Consented, unauthenticated view of a Cash Health Passport. |

---

**66 endpoints.**

## Worked examples

### Sign in

```bash
curl -s localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"owner@runway.demo","password":"demo1234"}'
```

Returns a token, the user, and every business the user is a member of with their
role in each.

### The dashboard in one request

```bash
curl -s 'localhost:8000/api/overview?as_of=2026-11-07' \
  -H "Authorization: Bearer $TOKEN" -H "X-Business-Id: $BIZ"
```

Returns the headline figures, the full 13-week forecast series, receivables ageing,
the next 30 days of obligations, the health score with all eight dimensions, the top
alert, the top four recommendations, the 30-day flow summary, data quality, and the
state versions and ledger fingerprint the whole thing was computed from.

### Run a scenario without saving it

```bash
curl -s 'localhost:8000/api/scenarios/quick-run?as_of=2026-11-07' \
  -H "Authorization: Bearer $TOKEN" -H "X-Business-Id: $BIZ" \
  -H 'content-type: application/json' -d '{
    "kind": "new_order",
    "parameters": {"order_value_paise": 150000000, "margin_pct": 0.18,
                   "advance_pct": 0.0, "credit_days": 60},
    "paths": 2500
  }'
```

Returns the baseline series, the scenario series, a nine-metric comparison table
with each change labelled, the scenario's economics (including the funding gap in
days), and the isolation guarantee.

### Rank alternative decisions

```bash
curl -s 'localhost:8000/api/scenarios/optimise?as_of=2026-11-07' \
  -H "Authorization: Bearer $TOKEN" -H "X-Business-Id: $BIZ" \
  -H 'content-type: application/json' -d '{
    "options": [
      {"key":"A","label":"Accept, no advance","kind":"new_order",
       "params":{"order_value_paise":150000000,"margin_pct":0.18,"advance_pct":0.0,"credit_days":60}},
      {"key":"B","label":"Accept with 30% advance","kind":"new_order",
       "params":{"order_value_paise":150000000,"margin_pct":0.18,"advance_pct":0.30,"credit_days":60}},
      {"key":"C","label":"Discount receivables","kind":"invoice_discounting",
       "params":{"max_amount_paise":100000000}}
    ]
  }'
```

Each option is simulated against the same baseline with the same random draws, then
scored. Infeasible options are returned with the policy they breach named.

### Ask the copilot

```bash
curl -s 'localhost:8000/api/copilot/ask?as_of=2026-11-07' \
  -H "Authorization: Bearer $TOKEN" -H "X-Business-Id: $BIZ" \
  -H 'content-type: application/json' \
  -d '{"question":"Should I accept a Rs 15 lakh order on 60-day terms?"}'
```

Returns the answer, which tool was selected and on what phrase, the state, the
evidence, the state versions it was computed from, suggested follow-ups, and a
state-appropriate disclaimer.

### Import a file (preview first)

```bash
curl -s 'localhost:8000/api/integrations/import?as_of=2026-11-07' \
  -H "Authorization: Bearer $TOKEN" -H "X-Business-Id: $BIZ" \
  -F adapter=bank_csv -F account_id=$ACCOUNT -F dry_run=true \
  -F file=@statement.csv
```

`dry_run=true` parses, deduplicates, categorises and matches, then rolls back.
Nothing is written until the same call is made with `dry_run=false`.

