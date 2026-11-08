# Testing

```bash
./run.sh test          # 210 backend tests on SQLite, ~75 s
./run.sh test-pg       # the identical suite against PostgreSQL, ~83 s
./run.sh test-web      # 75 frontend tests, ~1.2 s
./run.sh test-all      # backend + frontend
./run.sh verify        # ~5,000 accounting invariants, outside pytest
./run.sh audit-schema  # every VARCHAR against what the code can write
./run.sh evaluate      # regenerate every published accuracy figure
```

Tests run against a **freshly-seeded throwaway SQLite database** in a temp
directory, so the suite never touches the demo workspace and never depends on the
order tests happen to run in.

---

## What is tested, and why those things

| File | Tests | The question it answers |
|---|---:|---|
| `test_money.py` | 20 | Can the arithmetic lose a paisa? |
| `test_ledger_invariants.py` | 9 | Can the system create money? |
| `test_reconciliation.py` | 24 | Does matching behave correctly on messy real-world data? |
| `test_no_leakage.py` | 5 | Does the model see the future? |
| `test_forecast.py` | 17 | Are the intervals calibrated, reproducible and monotone? |
| `test_three_state.py` | 10 | Can a scenario touch reality? |
| `test_api_and_security.py` | 61 | Can one tenant see another's data? |
| `test_workflow_e2e.py` | 15 | Does the whole story actually work? |
| `test_pdf_and_portability.py` | 19 | Can a PDF be misread into the ledger? Will the schema survive PostgreSQL? |

### Frontend (`frontend/tests/`)

| File | Tests | The question it answers |
|---|---:|---|
| `format.test.ts` | 27 | Is a figure grouped the way an Indian reader expects? |
| `primitives.test.tsx` | 28 | Is the meaning carried by anything other than colour? |
| `api.test.ts` | 13 | Does every request carry its tenant and its as-of date? |
| `nav.test.ts` | 7 | Is any route dead or duplicated? |

---

## Running the same suite on both databases

```bash
./run.sh test          # SQLite      210 passed
./run.sh test-pg       # PostgreSQL  210 passed
```

`tests/conftest.py` reads `RUNWAY_TEST_DATABASE_URL` and falls back to a throwaway
SQLite file. That one hook is what turns "the ORM is portable" from a claim into a
check — and it immediately found four problems:

| Found | Why SQLite hid it |
|---|---|
| `predicted_snapshots.method` — 62 chars in a `VARCHAR(40)` | SQLite ignores length limits entirely |
| `predicted_snapshots.model_version` — 41 in a `VARCHAR(40)` | Same |
| `copilot_messages.generator` — 54 in a `VARCHAR(20)` | Same, **and the demo data never exercised it**: the long value only appears when an LLM reply is rejected |
| `func.iif()` in a test | SQLite-only function; the application was fine, the test was not |

## The tests that earn their place

### Leakage

```python
def test_customer_history_features_only_use_earlier_settlements():
    full    = features(invoices, TODAY)
    masked  = features([hide_settlements_after(cutoff, i) for i in invoices], cutoff)
    for inv_id in overlap:
        assert np.allclose(full[inv_id], masked[inv_id])
```

Recomputes every feature with the future hidden and requires the earlier invoices'
vectors to be **byte-identical**. If any feature peeked, this fails.

This is the test most ML pipelines do not have, and it is the reason the published
MAE means something.

### Monotonicity

```python
def test_paying_earlier_can_only_help():
    for i in f2.inflows: i.day_offset = max(0, i.day_offset - 14)
    assert simulate(f2, seed=7).min_cash_p50 >= base.min_cash_p50
```

Properties that must hold for *any* correct implementation. Both of these caught
real bugs:

- The **week-anchoring bug**: anchoring buckets on the calendar Monday discarded
  every payment arriving in the remainder of the current week, so "customers pay
  earlier" registered as destroying ₹1.88 lakh.
- The **horizon-clipping bug**: clipping flows past the horizon into the final
  bucket invented a ₹70 lakh jump in week 13.

Neither would have been found by looking at a chart.

### Scenario isolation

```python
def test_a_scenario_never_writes_to_the_ledger():
    before = (txn_count, invoice_count, allocation_count, total_settled)
    run_scenario(db, fifty_lakh_loan_scenario, ...)
    assert counts() == before
```

Runs a ₹50 lakh simulated loan and asserts nothing in the ledger moved.

### Tenant isolation

```python
def test_a_user_cannot_read_a_business_they_do_not_belong_to():
    r = client.get("/api/overview", headers={..., "X-Business-Id": other_business})
    assert r.status_code == 403
```

**403, not an empty result.** An empty result would be a silent failure mode.

### The copilot cannot invent a figure

```python
def test_a_figure_the_tools_did_not_produce_is_rejected():
    payload = {"data": {"cash_paise": 82400000}}
    assert verify_numbers("Your cash is Rs 8,24,000.", payload)[0] is True
    assert verify_numbers("Your cash is Rs 95,00,000.", payload)[0] is False
```

### Gateway fee double-allocation

```python
def test_reconciliation_is_idempotent():
    apply_match(db, txn, match_transaction(db, txn))
    first = invoice.settled_paise
    apply_match(db, txn, match_transaction(db, txn))
    assert invoice.settled_paise == first
```

This caught a real bug. The matcher added the gateway fee to the available amount
on *every* pass, so re-reconciling an already partly-matched settlement allocated
the MDR twice — ₹30,709 of money created from nothing. The fix introduced
`Transaction.settleable_paise`, and `test_no_allocation_exceeds_its_transaction`
found it in the first place.

### Schema portability

```python
def test_every_varchar_column_fits_what_the_code_can_write():
    r = subprocess.run([sys.executable, "scripts/audit_schema.py", "--quiet"], ...)
    assert r.returncode == 0
```

`scripts/audit_schema.py` checks every `VARCHAR` twice: against the longest value
**stored**, and against the longest value the **code could write** — derived from the
enums, the classifier's rule labels, the scenario kinds and the adapter keys. The
second check is the one that matters, because it catches columns the current data
happens not to fill.

```python
def test_no_sqlite_only_sql_anywhere():
    # func.iif, func.strftime, func.julianday, func.glob
```

Scans both the application and the test suite. A SQLite-only function passes every
local run and fails only on the deployment that matters.

### PDF extraction refuses rather than guesses

```python
def test_a_tax_rate_is_not_mistaken_for_a_tax_amount():
    # "CGST 9%: 10,094.19" — the rate comes first on the line.
    assert extract_fields(INTRASTATE).tax.value == pytest.approx(20188.37)
```

A real bug: reading the first number on the line gave 9 instead of 10,094.19, which
then failed to reconcile and quietly corrupted the invoice. The fix strips
percentage tokens and takes the rightmost figure, and the cross-check between
taxable + tax and the total now *raises* confidence when they agree and lowers it
when they do not.

```python
def test_an_unreadable_document_is_refused_not_guessed():
    assert extract_fields("scanned noise").usable is False
```

### The 26-week cross-check

```python
def test_a_revenue_shock_is_worse_over_two_quarters(db, business_id):
    r = long_horizon_check(db, business_id, TODAY, "revenue_shock", {"drop_pct": 0.20})
    assert r["closing_delta_at_26w_paise"] < r["closing_delta_at_13w_paise"] <= 0
```

And the negative case — a payment delay moves money already owed, so a longer
window adds nothing and the engine returns `None` rather than running a pointless
simulation.

### Every scenario in the catalogue executes

```python
def test_scenario_handlers_all_run():
    for entry in CATALOGUE:
        params = {p["key"]: p["default"] for p in entry["params"]}
        f, extras = apply_scenario(fi, entry["kind"], params, TODAY)
        assert "narrative" in extras
        assert len(simulate(f, paths=300).p50) == f.horizon_weeks + 1
```

A scenario cannot be added to the UI catalogue without being executable with its
published defaults.

---

## Accounting invariants

`scripts/verify_ledger.py` runs these directly against the live database — no
pytest, no fixtures, auditable by anyone:

1. `opening + credits − debits = closing`, per account, exactly.
2. `Σ allocations(invoice) ≤ invoice.total`.
3. `Σ allocations(transaction) ≤ transaction.settleable`.
4. `invoice.settled = Σ allocations(invoice)`.
5. No invoice settled beyond its total.

```
4,996 invariant checks run.
All accounting invariants hold.
```

---

## Parametrised coverage

Several suites iterate rather than sampling:

- **Every read endpoint** (31) is asserted to return 200 with a body.
- **Twelve of them** are asserted to return 401 without a token.
- **Twenty-two copilot questions** are asserted to route to the correct tool.
- **Twelve scenario questions** are asserted to produce the correct scenario kind.
- **Eight Indian bank narrations** are asserted to classify correctly.
- **Every scenario in the catalogue** is executed with its defaults.

---

## Not tested

Stated plainly:

- **No frontend tests.** The production build type-checks with `strict`, and the
  backend e2e suite covers the API contract the UI consumes, but there are no
  component or browser tests. Listed in `PROJECT_STATUS.md`.
- **No load testing.** Performance figures are single-request timings.
- **The PostgreSQL path is untested.** The ORM is portable by construction, but no
  test runs against Postgres in this build.
- **The LLM path is tested only for its guard rails** — fencing and numeric
  verification. Response quality with a live key is not asserted, because asserting
  on a model's prose would be a flaky test that teaches nothing.

---

## Adding a test

```python
# tests/conftest.py already provides:
#   seeded, business_id, second_business_id, db, client, owner_auth, ca_auth

def test_something(db, business_id):
    ...

def test_an_endpoint(client, owner_auth):
    r = client.get("/api/overview?as_of=2026-11-07", headers=owner_auth)
    assert r.status_code == 200
```

Tests that mutate should `db.rollback()` at the end, since the fixture database is
session-scoped and shared.
