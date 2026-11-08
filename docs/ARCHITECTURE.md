# Architecture

## The shape of the system

RUNWAY is a layered monolith. Everything runs in two processes — a FastAPI service
and a Next.js app — and that is a deliberate choice, revisited below.

```
L4  EXPERIENCE     Next.js web app · AI copilot · dashboards · scenario lab
L3  INTELLIGENCE   forecasting · risk · health · recommendations · optimiser
L2  DIGITAL TWIN   state manager (actual | predicted | simulated) · graph · timeline
L1  LEDGER         normalise · dedupe · classify · resolve · reconcile
L0  INTEGRATIONS   bank CSV · Tally XML · GST register · settlements · manual
```

A layer may call downwards and sideways within itself. It may not call upwards.
The one place this is enforced structurally rather than by convention is the
scenario engine: it has no database session at all, so it *cannot* write to the
ledger even by mistake.

## Request lifecycle

```
GET /api/overview?as_of=2026-11-07
  │
  ├─ middleware           request id, rate limit, timing
  ├─ get_current_user     decode JWT
  ├─ get_tenant           resolve membership → TenantContext (one business)
  │
  └─ get_bundle(db, business_id, as_of)
       ├─ ledger_fingerprint()          hash of the material ledger contents
       ├─ cache hit on (business, as_of, fingerprint)?  →  return
       │
       ├─ build_actual()                versioned snapshot from the ledger
       ├─ build_predicted()             train → predict → simulate → version
       ├─ analytics                     cash, receivables, payables, health,
       │                                concentration, obligations, anomalies
       ├─ risk                          stress tests, sensitivity, early warning
       ├─ recommend                     deterministic rules over all of the above
       └─ persist alerts + recommendations, return the bundle
```

Every screen and every copilot tool reads the **same bundle**. This is why two parts
of the product can never show two different answers to the same question — there is
only one computation.

## Why there is no Redis, Celery, or graph database

**No Redis.** The cache is an in-process dict keyed on
`(business_id, as_of, ledger_fingerprint)` with a 180-second TTL. The fingerprint is
the important part: a cache entry is invalidated by the *data changing*, not by a
clock. For one instance this is correct and has zero operational cost. A second
instance needs a shared store, and `PROJECT_STATUS.md` says so.

**No Celery.** A cold state rebuild is ~5 seconds, dominated by fitting four
gradient-boosting models; warm it is ~0.8 s and a cached read is ~3 ms. At MSME
scale — hundreds of counterparties, a few thousand transactions — a queue would add
a broker, a worker, a result backend and a whole class of partial-failure states to
save four seconds on a rare path. The threshold at which this flips is in §"When to
change these decisions".

**No graph database.** The relationship graph is 66 nodes and 65 edges for the demo
business, assembled from three relational queries in 56 ms. Neo4j would buy nothing
but a second datastore to operate. The flip point is multi-hop traversal — "which of
my customers share a supplier with my largest customer" — which is a real question
and would justify it.

**SQLite by default, PostgreSQL verified.** The single biggest obstacle to anyone
running a project like this is standing up its dependencies, and SQLite removes
that entirely. But "the ORM is portable" is the kind of claim that is wrong far
more often than it is checked, so it is checked: the schema migrates onto
PostgreSQL, the full workspace seeds, and the identical 210-test suite passes
(`./run.sh test-pg`).

Doing that found four problems a SQLite-only project would have shipped:

| Problem | Why SQLite hid it |
|---|---|
| `predicted_snapshots.method` held 62 characters in a `VARCHAR(40)` | SQLite ignores length limits entirely |
| `predicted_snapshots.model_version` held 41 in a `VARCHAR(40)` | Same |
| `copilot_messages.generator` could hold 54 in a `VARCHAR(20)` | Same — and the demo data never exercised it, because that value only appears when an LLM reply is rejected |
| A test used `func.iif()` | SQLite-only; the application was portable, the test was not |

`scripts/audit_schema.py` now checks every `VARCHAR` against both the stored data
*and* the longest value the code could write, derived from the enums, classifier
rule labels, scenario kinds and adapter keys. It runs in CI as a test.

**Migrations.** Alembic, with `env.py` reading the URL from the application's own
settings rather than `alembic.ini` — so a migration can never target a different
database than the app. SQLite gets `render_as_batch` automatically, which is what
lets one revision script run on both backends. A freshly-created schema is stamped
at head, so the zero-setup path and the migration path do not fight.

## Money

Every monetary value is an **integer number of paise** (`BigInteger`). This is the
single most consequential decision in the codebase.

Floating point appears only inside statistical models — a Monte Carlo path is a
float array by necessity — and every value crossing back into the ledger is rounded
once, at the boundary, in `app.core.money.to_paise`. Proportional splits use the
largest-remainder method so `sum(parts) == total` exactly.

The payoff is that `opening + credits − debits = closing` holds *exactly* across
~5,000 checks in `scripts/verify_ledger.py`, rather than approximately.

## Tenancy

Every tenant-scoped table carries `business_id`. Every request resolves a
`TenantContext` from the caller's **membership**, never from a body parameter. There
is no code path in which a business id arrives from the client and is trusted.

The copilot tools take this further: **no tool accepts a business id at all**. They
receive a `TwinBundle` that was constructed for exactly one business, so there is no
parameter through which data could cross tenants even if a model were persuaded to
try. `tests/test_copilot.py::test_tool_schema_exposes_no_business_parameter` asserts
this against the published schema.

## State versioning

```
BusinessState (immutable header)
  ├── ActualSnapshot      cash, AR, AP, working capital at a point in time
  ├── PredictedSnapshot   forecast series, assumptions, model version, seed
  └── SimulatedSnapshot   scenario parameters, outputs, both baseline pointers
```

A new version **supersedes**; it never replaces. `status` moves from `current` to
`superseded` and the row stays queryable forever. This is not tidiness — it is the
only way forecast accuracy can be measured honestly, because scoring a forecast
requires the forecast as it was made, not as it would be made today.

`ledger_fingerprint` on every state proves which ledger produced it:

```python
sha256(f"{as_of}|{txn_count}|{txn_sum}|{txn_max_updated}|"
       f"{inv_count}|{inv_settled_sum}|{inv_total_sum}")[:40]
```

Two states with the same fingerprint describe the same financial reality.

## Scenario isolation

```python
def apply_scenario(baseline, kind, params, as_of):
    fi = baseline.copy()        # deepcopy, in exactly one place
    extras = HANDLERS[kind](fi, params, as_of)
    return fi, extras
```

Three properties follow from this shape:

1. **Isolation is structural.** The handler receives a copy. No handler has a
   database session. There is no path from a scenario to a ledger table.
2. **Comparability is guaranteed.** Baseline and scenario are evaluated by the same
   simulator on the same inputs object, differing only in the mutation.
3. **Reproducibility is free.** Same baseline + same parameters + same seed ⇒
   identical output, asserted by `test_training_is_reproducible` and
   `test_same_seed_gives_identical_results`.

## Event flow on new data

```
import / correction / manual entry
   → ledger write
   → invalidate(business_id)
   → next read: fingerprint changes → new ActualState v(n+1)
                                    → new PredictedState v(m+1)
                                    → previous versions preserved
                                    → saved scenarios keep their original baseline
```

A saved scenario pins `baseline_actual_state_id` and `baseline_predicted_state_id`.
Re-running it uses those, not the current state, so a comparison made last month
stays the comparison that was made — a scenario that silently re-baselined would
make every recorded decision unauditable.

## Component inventory

| Layer | Modules | Responsibility |
|---|---|---|
| L0 | `integrations/` | Adapter protocol, six importers, honest status declarations |
| L1 | `ledger/` | `normalise`, `classifier`, `entities`, `reconciliation`, `asof` |
| L2 | `financial_states/`, `digital_twin/` | State manager, graph, timeline, scenario engine, optimiser, twin service |
| L3 | `analytics/`, `forecast/`, `risk/`, `recommend/` | Everything that produces a number |
| L4 | `api/`, `copilot/` | 62 endpoints, 22 tools, routing, LLM layer |

## Failure modes and how they are handled

| Failure | Handling |
|---|---|
| Malformed import row | Rejected with a row number and a reason, listed in the import report. Never silently skipped. |
| Ambiguous counterparty | No match is recorded; the reason names both candidates and their scores. |
| Low-confidence category | Written with its confidence; surfaced under "needs review" rather than accepted. |
| Suspected duplicate | Imported and flagged. Never deleted — a business genuinely can pay the same amount twice. |
| Too little history to train | Falls back to the per-customer median with the reason recorded in the model metrics. |
| No forecast has matured | Accuracy is reported as unavailable with an explanation, never as a number. |
| LLM unavailable or wrong | Deterministic renderer, with the reason recorded in `generator`. |
| LLM states an unverified figure | Reply discarded; deterministic renderer used instead. |
| Stale ledger | Data-quality score drops, a warning appears on screen, and the staleness is in days. |

## Performance

Measured on the demo workspace (1,864 transactions, 1,303 invoices):

| Operation | Time |
|---|---|
| Monte Carlo, 4,000 paths × 14 weeks | ~50 ms |
| Full bundle, cold (includes model fitting) | ~5 s |
| Full bundle, warm | ~0.8 s |
| Cached read | ~3 ms |
| Relationship graph | ~56 ms |
| Scenario quick-run (2 × 2,500 paths) | ~150 ms |
| Eight stress tests | ~100 ms |

The Monte Carlo is fully vectorised: all paths advance together as NumPy arrays with
scatter-adds, never a Python loop over paths. That is what makes the Scenario Lab
feel like a slider rather than a batch job.

## When to change these decisions

| Decision | Revisit when |
|---|---|
| SQLite | More than one writer, or data worth a migration path |
| In-process cache | More than one API instance |
| Inline state rebuild | p95 import latency matters, or models grow past a few seconds |
| Relational graph | Multi-hop traversal becomes a product feature |
| Monolith | Teams need independent deploy cadence — not before |
| Inline OCR | Scanned-PDF volume makes a 60 s timeout a user-visible problem |
| Direct quant implementations | A technique outgrows ~200 lines of auditable code |
