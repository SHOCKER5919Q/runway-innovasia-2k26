# Digital twin data model

The 28 tables, grouped by what they are for. Column-level detail is in
`DATA_DICTIONARY.md`.

## Tenancy and access

| Table | Purpose |
|---|---|
| `businesses` | The tenant. Identity, industry, GSTIN, MSME class, and the **financial policies** that drive the engine: safety buffer, target runway, maximum concentration, maximum borrowing APR, minimum order margin, risk appetite. |
| `users` | Accounts. Password hash, preferred language, accountant flag. |
| `memberships` | user × business × role (`owner`, `manager`, `accountant`, `viewer`) with purpose scopes. Every request resolves its tenant from here. |
| `consents` | Purpose-limited, expiring, revocable permissions: AA fetch, passport sharing, accountant access. |
| `audit_log` | Who did what, to which entity, with what detail and from where. |

## Ledger

| Table | Purpose |
|---|---|
| `accounts` | Bank, cash, FD, overdraft, wallet. Opening balance and date, overdraft limit, **restricted amount** (lien-marked), source system. |
| `counterparties` | Customers and suppliers. Normalised name and aliases for resolution, sector, region, **MSME class** (drives 43B(h)), credit terms, early-payment discount, contacts. |
| `transactions` | The canonical money movement. Always a positive amount plus a direction. Carries `gross`/`fee` for gateway settlements, a `fingerprint` for deduplication, `evidence`, `recon_status`, `category` with its confidence and rule, the verbatim source row, and the full transformation log. |
| `invoices` | Sales and purchase. Taxable, tax, total, settled, written off; issue, due, first-payment and settled dates; GST rate; `has_written_agreement` (drives the 15-vs-45-day MSMED window). |
| `allocations` | The (transaction, invoice, amount) triple. **This is what makes partial payments, split settlements and gateway fees representable** — and what the no-money-created invariants are checked against. |
| `obligations` | GST, TDS, payroll, PF/ESI, rent, EMI, insurance. Due date, amount, evidence class, recurrence, and whether cash is ring-fenced. |
| `loans` | Lender, kind, principal, outstanding, rate, EMI and day. |
| `import_batches` | Per import: rows seen, imported, duplicated, rejected, plus errors and a report. |

## The three states

| Table | Purpose |
|---|---|
| `business_states` | Immutable header for every state of every type. Version, as-of, created-at, lineage, engine version, **ledger fingerprint**, data quality, status, trigger. |
| `actual_snapshots` | Cash, restricted, committed, available, overdraft headroom, receivables and overdue, payables and overdue, loans, 30-day revenue and expense, weekly net burn, working capital. |
| `predicted_snapshots` | Model version, horizon, method, seed, runway P10/P50, minimum cash, first breach week, breach probability, VaR, CVaR, assumptions, and the full series. |
| `simulated_snapshots` | Scenario id, **both** baseline pointers, parameters, outputs, runway, minimum cash, peak working capital, breach probability, expected profit, financing cost, seed. |
| `state_comparisons` | Stored comparisons with their type and metrics. |
| `forecast_points` | One flattened row per horizon week: P10/P50/P90 and, once the week passes, the **resolved actual**. This table is what makes accuracy measurable. |
| `payment_predictions` | One row per open invoice per forecast run: delay quantiles, predicted date, probabilities at 7/15/30 days, confidence, driver contributions, and the **resolved actual delay**. |
| `model_runs` | Training metadata and metrics per model version. |

## Decisions and intelligence

| Table | Purpose |
|---|---|
| `scenarios` | Name, kind, parameters, pinned baselines, parent (for branches), origin, last run. |
| `scenario_decisions` | What the owner decided, when, with what note, and the realised outcome once measured. |
| `alerts` | Code, level, title, and the six required fields: what happened, why it matters, evidence, impact, recommended action, what happens if ignored. Deduplicated by key; closed automatically when the condition stops holding. |
| `recommendations` | Title, priority, the five published score terms, triggering evidence, expected effect, downside, required action, deadline, confidence, explanation, approval requirement. |
| `copilot_messages` | Role, content, tool calls, evidence, **state references**, language and generator (`deterministic` or `llm`). |
| `twin_events` | The activity log: every state rebuild, forecast run and scenario, with a summary. |
| `shared_reports` | Cash Health Passport snapshots issued under a consent, with token, recipient, expiry, revocation and view count. |

## Design notes

**Money is `BigInteger` paise, everywhere.** No `Numeric`, no `Float`, no exceptions.

**Evidence travels with the value.** `transactions`, `invoices` and `obligations`
each carry an `evidence` column, so a figure's reliability is a property of the
figure rather than of the screen it happens to appear on.

**Provenance is never discarded.** `raw_json` holds the source row verbatim;
`transform_log_json` holds every step applied to it, including owner corrections.

**JSONB is for genuinely open-ended metadata only.** Anything queried or joined has
a real column. Assumption bags, simulation series and score terms are JSON because
their shape legitimately varies by model version; nothing that needs an index is.

**States are append-only.** Superseding sets a status; it never deletes. Old
forecasts remain queryable forever, because scoring a forecast requires the forecast
as it was made.
