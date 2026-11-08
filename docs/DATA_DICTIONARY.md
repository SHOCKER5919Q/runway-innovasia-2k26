# Data dictionary

28 tables. Column-level detail generated from the live schema.

## Conventions

**Money is `BIGINT` paise.** Every column ending `_paise` is an integer number of
paise (1 rupee = 100 paise). There is no `NUMERIC` and no `FLOAT` anywhere in the
monetary path. This is what makes `opening + credits − debits = closing` hold
exactly rather than approximately.

**Ids are 32-character hex strings** (`uuid4().hex`), generated application-side so
an object has an identity before it is flushed.

**`business_id`** appears on every tenant-scoped table and is always resolved from
the caller's membership.

**`evidence`** records a value's place in the hierarchy: `verified_actual` >
`imported_actual` > `owner_estimate` > `model_prediction` > `scenario_assumption` >
`simulation_output`. A value may be demoted freely; promotion is an audited action.

**JSON columns** are used for genuinely open-ended metadata only — assumption bags,
simulation series, score terms. Anything queried or joined has a real column.

---

## Tenancy and access

### `businesses`

The tenant. Carries the **financial policies** that drive the engine: safety buffer, target runway, maximum concentration, maximum borrowing APR, minimum order margin, risk appetite.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `name` | VARCHAR(200) | no |  |  |
| `legal_name` | VARCHAR(200) | yes |  |  |
| `industry` | VARCHAR(40) | no | `wholesale_distribution` |  |
| `gstin` | VARCHAR(15) | yes |  |  |
| `city` | VARCHAR(80) | yes |  |  |
| `state_code` | VARCHAR(4) | yes |  |  |
| `fiscal_year_start_month` | INTEGER | no | `4` |  |
| `msme_class` | VARCHAR(10) | no | `small` |  |
| `udyam_number` | VARCHAR(32) | yes |  |  |
| `is_demo` | BOOLEAN | no | `True` |  |
| `demo_scenario` | VARCHAR(40) | yes |  |  |
| `safety_buffer_paise` | BIGINT | no | `0` | integer paise |
| `target_runway_weeks` | FLOAT | no | `8.0` |  |
| `max_customer_concentration` | FLOAT | no | `0.35` |  |
| `max_borrowing_apr` | FLOAT | no | `0.24` |  |
| `min_order_margin` | FLOAT | no | `0.1` |  |
| `risk_appetite` | VARCHAR(16) | no | `balanced` |  |
| `locale` | VARCHAR(8) | no | `en-IN` |  |
| `settings_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

### `users`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `email` | VARCHAR(200) | no |  |  |
| `full_name` | VARCHAR(160) | no | `` |  |
| `phone` | VARCHAR(20) | yes |  |  |
| `password_hash` | VARCHAR(300) | no |  |  |
| `is_active` | BOOLEAN | no | `True` |  |
| `is_accountant` | BOOLEAN | no | `False` |  |
| `preferred_language` | VARCHAR(8) | no | `en` |  |
| `last_login_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_users_email` (email)

### `memberships`

user × business × role. Every request resolves its tenant from here, never from a request body.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `user_id` | VARCHAR(32) | no |  | → `users` |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `role` | VARCHAR(20) | no | `owner` |  |
| `scopes_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_memberships_business_id` (business_id), `ix_memberships_user_id` (user_id)

### `consents`

Purpose-limited, expiring, revocable. Backs AA consent, passport sharing and accountant access.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `purpose` | VARCHAR(120) | no |  |  |
| `scope_json` | JSON | no |  |  |
| `granted_by_user_id` | VARCHAR(32) | yes |  |  |
| `grantee` | VARCHAR(200) | yes |  |  |
| `granted_at` | DATETIME | no |  |  |
| `expires_at` | DATETIME | yes |  |  |
| `revoked_at` | DATETIME | yes |  |  |
| `token` | VARCHAR(64) | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_consents_business_id` (business_id), `ix_consents_token` (token)

### `audit_log`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER | no |  | **PK** |
| `at` | DATETIME | no |  |  |
| `business_id` | VARCHAR(32) | yes |  |  |
| `user_id` | VARCHAR(32) | yes |  |  |
| `action` | VARCHAR(80) | no |  |  |
| `entity` | VARCHAR(60) | yes |  |  |
| `entity_id` | VARCHAR(64) | yes |  |  |
| `detail_json` | JSON | no |  |  |
| `ip` | VARCHAR(64) | yes |  |  |

Indexes: `ix_audit_log_action` (action), `ix_audit_log_at` (at), `ix_audit_log_business_id` (business_id)

## Ledger

### `accounts`

`restricted_paise` marks lien-marked balances that cannot fund operations. `overdraft_limit_paise` is credit and is reported separately from cash.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `name` | VARCHAR(160) | no |  |  |
| `kind` | VARCHAR(20) | no | `current` |  |
| `bank_name` | VARCHAR(120) | yes |  |  |
| `masked_number` | VARCHAR(40) | yes |  |  |
| `currency` | VARCHAR(3) | no | `INR` |  |
| `opening_balance_paise` | BIGINT | no | `0` | integer paise |
| `opening_date` | DATE | no |  |  |
| `overdraft_limit_paise` | BIGINT | no | `0` | integer paise |
| `restricted_paise` | BIGINT | no | `0` | integer paise |
| `is_active` | BOOLEAN | no | `True` |  |
| `source_system` | VARCHAR(40) | no | `manual` |  |
| `last_synced_at` | DATETIME | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_accounts_business_id` (business_id)

### `counterparties`

`msme_class` drives the MSMED/43B(h) deadline. `normalised_name` and `aliases_json` drive entity resolution.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `name` | VARCHAR(200) | no |  |  |
| `normalised_name` | VARCHAR(200) | no |  |  |
| `party_type` | VARCHAR(20) | no | `customer` |  |
| `gstin` | VARCHAR(15) | yes |  |  |
| `sector` | VARCHAR(60) | yes |  |  |
| `region` | VARCHAR(60) | yes |  |  |
| `msme_class` | VARCHAR(10) | yes |  |  |
| `credit_days` | INTEGER | no | `30` |  |
| `credit_limit_paise` | BIGINT | no | `0` | integer paise |
| `early_payment_discount_pct` | FLOAT | no | `0.0` |  |
| `early_payment_days` | INTEGER | no | `0` |  |
| `contact_name` | VARCHAR(120) | yes |  |  |
| `contact_phone` | VARCHAR(20) | yes |  |  |
| `contact_email` | VARCHAR(160) | yes |  |  |
| `aliases_json` | JSON | no |  |  |
| `notes` | TEXT | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_counterparties_business_id` (business_id), `ix_counterparties_gstin` (gstin), `ix_counterparties_normalised_name` (normalised_name), `ix_cp_business_name` (business_id, name)

### `transactions`

Amount is always positive; `direction` carries the sign. `gross_paise`/`fee_paise` hold a gateway settlement's components. `raw_json` is the source row verbatim and `transform_log_json` every step applied to it.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `account_id` | VARCHAR(32) | no |  | → `accounts` |
| `counterparty_id` | VARCHAR(32) | yes |  | → `counterparties` |
| `import_batch_id` | VARCHAR(32) | yes |  |  |
| `source_system` | VARCHAR(60) | no | `manual` |  |
| `source_ref` | VARCHAR(120) | yes |  |  |
| `value_date` | DATE | no |  |  |
| `posting_date` | DATE | yes |  |  |
| `amount_paise` | BIGINT | no |  | integer paise |
| `direction` | VARCHAR(8) | no |  |  |
| `currency` | VARCHAR(3) | no | `INR` |  |
| `narration` | TEXT | no | `` |  |
| `reference_no` | VARCHAR(80) | yes |  |  |
| `category` | VARCHAR(40) | no | `uncategorised` |  |
| `category_confidence` | FLOAT | no | `0.0` |  |
| `category_source` | VARCHAR(60) | no | `rules` |  |
| `evidence` | VARCHAR(24) | no | `imported_actual` | evidence hierarchy |
| `recon_status` | VARCHAR(24) | no | `unreconciled` |  |
| `allocated_paise` | BIGINT | no | `0` | integer paise |
| `gross_paise` | BIGINT | yes |  | integer paise |
| `fee_paise` | BIGINT | no | `0` | integer paise |
| `is_reversal_of` | VARCHAR(32) | yes |  |  |
| `fingerprint` | VARCHAR(64) | no | `` |  |
| `duplicate_of` | VARCHAR(32) | yes |  |  |
| `raw_json` | JSON | no |  |  |
| `transform_log_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_transactions_account_id` (account_id), `ix_transactions_business_id` (business_id), `ix_transactions_category` (category), `ix_transactions_import_batch_id` (import_batch_id), `ix_txn_business_date` (business_id, value_date), `ix_txn_business_recon` (business_id, recon_status), `ix_txn_fingerprint` (business_id, fingerprint)

### `invoices`

`has_written_agreement` selects the 45-day or 15-day MSMED window. `first_payment_date` and `settled_date` are what make point-in-time reconstruction possible.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `counterparty_id` | VARCHAR(32) | no |  | → `counterparties` |
| `kind` | VARCHAR(10) | no | `sales` |  |
| `invoice_no` | VARCHAR(60) | no |  |  |
| `issue_date` | DATE | no |  |  |
| `due_date` | DATE | no |  |  |
| `credit_days` | INTEGER | no | `30` |  |
| `taxable_paise` | BIGINT | no | `0` | integer paise |
| `tax_paise` | BIGINT | no | `0` | integer paise |
| `total_paise` | BIGINT | no |  | integer paise |
| `settled_paise` | BIGINT | no | `0` | integer paise |
| `written_off_paise` | BIGINT | no | `0` | integer paise |
| `status` | VARCHAR(16) | no | `open` |  |
| `gst_rate` | FLOAT | no | `0.18` |  |
| `place_of_supply` | VARCHAR(4) | yes |  |  |
| `has_written_agreement` | BOOLEAN | no | `True` |  |
| `source_system` | VARCHAR(40) | no | `manual` |  |
| `evidence` | VARCHAR(24) | no | `imported_actual` | evidence hierarchy |
| `first_payment_date` | DATE | yes |  |  |
| `settled_date` | DATE | yes |  |  |
| `notes` | TEXT | yes |  |  |
| `raw_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_inv_business_due` (business_id, due_date), `ix_inv_business_kind_status` (business_id, kind, status), `ix_invoices_business_id` (business_id), `ix_invoices_counterparty_id` (counterparty_id), `ix_invoices_due_date` (due_date), `ix_invoices_status` (status)

### `allocations`

The (transaction, invoice, amount) triple. This is what makes partial payments, split settlements and gateway fees representable, and what the no-money-created invariants are checked against.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `transaction_id` | VARCHAR(32) | no |  | → `transactions` |
| `invoice_id` | VARCHAR(32) | no |  | → `invoices` |
| `amount_paise` | BIGINT | no |  | integer paise |
| `method` | VARCHAR(24) | no | `auto` |  |
| `confidence` | FLOAT | no | `1.0` |  |
| `rationale` | VARCHAR(300) | no | `` |  |
| `confirmed_by_user_id` | VARCHAR(32) | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_alloc_inv` (invoice_id), `ix_alloc_txn` (transaction_id), `ix_allocations_business_id` (business_id)

### `obligations`

`evidence` distinguishes a contractual commitment from a RUNWAY estimate. `reserve_cash` determines whether the amount is deducted from available liquidity.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `kind` | VARCHAR(20) | no | `other` |  |
| `label` | VARCHAR(200) | no |  |  |
| `due_date` | DATE | no |  |  |
| `amount_paise` | BIGINT | no |  | integer paise |
| `evidence` | VARCHAR(24) | no | `owner_estimate` | evidence hierarchy |
| `is_recurring` | BOOLEAN | no | `False` |  |
| `recurrence` | VARCHAR(20) | yes |  |  |
| `is_paid` | BOOLEAN | no | `False` |  |
| `paid_transaction_id` | VARCHAR(32) | yes |  |  |
| `reserve_cash` | BOOLEAN | no | `False` |  |
| `counterparty_id` | VARCHAR(32) | yes |  |  |
| `source_system` | VARCHAR(40) | no | `derived` |  |
| `detail_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_oblig_business_due` (business_id, due_date), `ix_obligations_business_id` (business_id)

### `loans`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `lender` | VARCHAR(160) | no |  |  |
| `kind` | VARCHAR(30) | no | `term` |  |
| `principal_paise` | BIGINT | no | `0` | integer paise |
| `outstanding_paise` | BIGINT | no | `0` | integer paise |
| `annual_rate` | FLOAT | no | `0.14` |  |
| `emi_paise` | BIGINT | no | `0` | integer paise |
| `emi_day` | INTEGER | no | `5` |  |
| `start_date` | DATE | yes |  |  |
| `end_date` | DATE | yes |  |  |
| `is_active` | BOOLEAN | no | `True` |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_loans_business_id` (business_id)

### `import_batches`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `adapter` | VARCHAR(60) | no |  |  |
| `filename` | VARCHAR(300) | yes |  |  |
| `status` | VARCHAR(20) | no | `pending` |  |
| `rows_seen` | INTEGER | no | `0` |  |
| `rows_imported` | INTEGER | no | `0` |  |
| `rows_duplicate` | INTEGER | no | `0` |  |
| `rows_rejected` | INTEGER | no | `0` |  |
| `errors_json` | JSON | no |  |  |
| `report_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_import_batches_business_id` (business_id)

## Three-state architecture

### `business_states`

Immutable. `ledger_fingerprint` proves which ledger produced the state; `source_state_id` carries the lineage. Superseding sets `status`; it never deletes.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `state_type` | VARCHAR(12) | no |  |  |
| `version` | INTEGER | no |  |  |
| `as_of_date` | DATE | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `source_state_id` | VARCHAR(32) | yes |  |  |
| `engine_version` | VARCHAR(20) | no | `0.9.0` |  |
| `ledger_fingerprint` | VARCHAR(64) | no | `` |  |
| `data_quality_json` | JSON | no |  |  |
| `status` | VARCHAR(16) | no | `current` |  |
| `trigger` | VARCHAR(80) | no | `manual` |  |

Indexes: `ix_business_states_business_id` (business_id), `ix_business_states_created_at` (created_at), `ix_state_lookup` (business_id, state_type, version)

### `actual_snapshots`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `state_id` | VARCHAR(32) | no |  | **PK** · → `business_states` |
| `business_id` | VARCHAR(32) | no |  |  |
| `as_of_date` | DATE | no |  |  |
| `cash_paise` | BIGINT | no | `0` | integer paise |
| `restricted_paise` | BIGINT | no | `0` | integer paise |
| `committed_paise` | BIGINT | no | `0` | integer paise |
| `available_liquidity_paise` | BIGINT | no | `0` | integer paise |
| `overdraft_headroom_paise` | BIGINT | no | `0` | integer paise |
| `receivables_paise` | BIGINT | no | `0` | integer paise |
| `receivables_overdue_paise` | BIGINT | no | `0` | integer paise |
| `payables_paise` | BIGINT | no | `0` | integer paise |
| `payables_overdue_paise` | BIGINT | no | `0` | integer paise |
| `loan_outstanding_paise` | BIGINT | no | `0` | integer paise |
| `revenue_30d_paise` | BIGINT | no | `0` | integer paise |
| `expense_30d_paise` | BIGINT | no | `0` | integer paise |
| `net_burn_weekly_paise` | BIGINT | no | `0` | integer paise |
| `working_capital_paise` | BIGINT | no | `0` | integer paise |
| `detail_json` | JSON | no |  |  |

Indexes: `ix_actual_snapshots_business_id` (business_id)

### `predicted_snapshots`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `state_id` | VARCHAR(32) | no |  | **PK** · → `business_states` |
| `business_id` | VARCHAR(32) | no |  |  |
| `baseline_actual_state_id` | VARCHAR(32) | no |  |  |
| `model_version` | VARCHAR(120) | no | `` |  |
| `horizon_weeks` | INTEGER | no | `13` |  |
| `method` | VARCHAR(120) | no | `ledger_driven_monte_carlo` |  |
| `seed` | INTEGER | no | `0` |  |
| `runway_weeks_p50` | FLOAT | no | `0.0` |  |
| `runway_weeks_p10` | FLOAT | no | `0.0` |  |
| `min_cash_p50_paise` | BIGINT | no | `0` | integer paise |
| `min_cash_p10_paise` | BIGINT | no | `0` | integer paise |
| `first_breach_week` | INTEGER | yes |  |  |
| `breach_probability` | FLOAT | no | `0.0` |  |
| `liquidity_var_paise` | BIGINT | no | `0` | integer paise |
| `liquidity_cvar_paise` | BIGINT | no | `0` | integer paise |
| `assumptions_json` | JSON | no |  |  |
| `series_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |

Indexes: `ix_predicted_snapshots_baseline_actual_state_id` (baseline_actual_state_id), `ix_predicted_snapshots_business_id` (business_id)

### `simulated_snapshots`

Carries **both** baseline pointers, so a saved comparison stays honest after the ledger moves on.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `state_id` | VARCHAR(32) | no |  | **PK** · → `business_states` |
| `business_id` | VARCHAR(32) | no |  |  |
| `scenario_id` | VARCHAR(32) | no |  |  |
| `baseline_actual_state_id` | VARCHAR(32) | no |  |  |
| `baseline_predicted_state_id` | VARCHAR(32) | no |  |  |
| `parameters_json` | JSON | no |  |  |
| `outputs_json` | JSON | no |  |  |
| `runway_weeks_p50` | FLOAT | no | `0.0` |  |
| `min_cash_p50_paise` | BIGINT | no | `0` | integer paise |
| `min_cash_p10_paise` | BIGINT | no | `0` | integer paise |
| `peak_wc_requirement_paise` | BIGINT | no | `0` | integer paise |
| `breach_probability` | FLOAT | no | `0.0` |  |
| `expected_profit_paise` | BIGINT | no | `0` | integer paise |
| `financing_cost_paise` | BIGINT | no | `0` | integer paise |
| `seed` | INTEGER | no | `0` |  |
| `created_at` | DATETIME | no |  |  |

Indexes: `ix_simulated_snapshots_business_id` (business_id), `ix_simulated_snapshots_scenario_id` (scenario_id)

### `state_comparisons`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `source_state_id` | VARCHAR(32) | no |  |  |
| `target_state_id` | VARCHAR(32) | no |  |  |
| `comparison_type` | VARCHAR(40) | no |  |  |
| `metrics_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |

Indexes: `ix_state_comparisons_business_id` (business_id)

### `forecast_points`

One flattened row per horizon week. `actual_paise` is filled once the week passes. **This table is what makes accuracy measurable.**

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `predicted_state_id` | VARCHAR(32) | no |  |  |
| `created_on` | DATE | no |  |  |
| `target_week_start` | DATE | no |  |  |
| `horizon_weeks` | INTEGER | no |  |  |
| `metric` | VARCHAR(32) | no | `closing_cash` |  |
| `p10_paise` | BIGINT | no | `0` | integer paise |
| `p50_paise` | BIGINT | no | `0` | integer paise |
| `p90_paise` | BIGINT | no | `0` | integer paise |
| `actual_paise` | BIGINT | yes |  | integer paise |
| `resolved_at` | DATETIME | yes |  |  |

Indexes: `ix_forecast_points_business_id` (business_id), `ix_forecast_points_predicted_state_id` (predicted_state_id), `ix_fp_lookup` (business_id, target_week_start, predicted_state_id)

### `payment_predictions`

One row per open invoice per forecast run, with `actual_delay_days` resolved on settlement.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `invoice_id` | VARCHAR(32) | no |  |  |
| `predicted_state_id` | VARCHAR(32) | yes |  |  |
| `created_at` | DATETIME | no |  |  |
| `model_version` | VARCHAR(120) | no | `` |  |
| `predicted_delay_days_p50` | FLOAT | no | `0.0` |  |
| `predicted_delay_days_p10` | FLOAT | no | `0.0` |  |
| `predicted_delay_days_p90` | FLOAT | no | `0.0` |  |
| `predicted_pay_date` | DATE | no |  |  |
| `prob_within_7` | FLOAT | no | `0.0` |  |
| `prob_within_15` | FLOAT | no | `0.0` |  |
| `prob_within_30` | FLOAT | no | `0.0` |  |
| `prob_default` | FLOAT | no | `0.0` |  |
| `confidence` | FLOAT | no | `0.0` |  |
| `drivers_json` | JSON | no |  |  |
| `actual_delay_days` | FLOAT | yes |  |  |
| `resolved_at` | DATETIME | yes |  |  |

Indexes: `ix_payment_predictions_business_id` (business_id), `ix_payment_predictions_invoice_id` (invoice_id), `ix_payment_predictions_predicted_state_id` (predicted_state_id), `ix_pp_lookup` (business_id, invoice_id, created_at)

### `model_runs`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `model_name` | VARCHAR(60) | no |  |  |
| `model_version` | VARCHAR(120) | no |  |  |
| `trained_at` | DATETIME | no |  |  |
| `n_train` | INTEGER | no | `0` |  |
| `n_test` | INTEGER | no | `0` |  |
| `metrics_json` | JSON | no |  |  |
| `params_json` | JSON | no |  |  |
| `notes` | TEXT | no | `` |  |

Indexes: `ix_model_runs_business_id` (business_id)

## Decisions and intelligence

### `scenarios`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `name` | VARCHAR(160) | no |  |  |
| `kind` | VARCHAR(32) | no | `composite` |  |
| `description` | TEXT | no | `` |  |
| `parameters_json` | JSON | no |  |  |
| `baseline_actual_state_id` | VARCHAR(32) | yes |  |  |
| `baseline_predicted_state_id` | VARCHAR(32) | yes |  |  |
| `parent_scenario_id` | VARCHAR(32) | yes |  |  |
| `created_by_user_id` | VARCHAR(32) | yes |  |  |
| `origin` | VARCHAR(20) | no | `ui` |  |
| `last_run_state_id` | VARCHAR(32) | yes |  |  |
| `is_archived` | BOOLEAN | no | `False` |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_scenarios_business_id` (business_id)

### `scenario_decisions`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `scenario_id` | VARCHAR(32) | no |  |  |
| `status` | VARCHAR(20) | no | `draft` |  |
| `decided_by_user_id` | VARCHAR(32) | yes |  |  |
| `decided_at` | DATETIME | yes |  |  |
| `implementation_date` | DATE | yes |  |  |
| `note` | TEXT | no | `` |  |
| `actual_refs_json` | JSON | no |  |  |
| `outcome_json` | JSON | no |  |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_scenario_decisions_business_id` (business_id), `ix_scenario_decisions_scenario_id` (scenario_id)

### `alerts`

Carries the six required fields. Deduplicated by `dedupe_key`; closed automatically when the condition stops holding.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `code` | VARCHAR(50) | no |  |  |
| `level` | VARCHAR(12) | no | `info` |  |
| `title` | VARCHAR(220) | no |  |  |
| `what_happened` | TEXT | no | `` |  |
| `why_it_matters` | TEXT | no | `` |  |
| `evidence_json` | JSON | no |  |  |
| `impact_paise` | BIGINT | no | `0` | integer paise |
| `impact_date` | DATE | yes |  |  |
| `recommended_action` | TEXT | no | `` |  |
| `if_ignored` | TEXT | no | `` |  |
| `state_id` | VARCHAR(32) | yes |  |  |
| `is_open` | BOOLEAN | no | `True` |  |
| `acknowledged_at` | DATETIME | yes |  |  |
| `first_seen_at` | DATETIME | no |  |  |
| `dedupe_key` | VARCHAR(120) | no | `` |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_alert_business_level` (business_id, level, is_open), `ix_alerts_business_id` (business_id), `ix_alerts_code` (code), `ix_alerts_dedupe_key` (dedupe_key)

### `recommendations`

`score_json` holds the five published ranking terms, so the order can be audited.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  | → `businesses` |
| `code` | VARCHAR(50) | no |  |  |
| `title` | VARCHAR(220) | no |  |  |
| `priority` | INTEGER | no | `50` |  |
| `score_json` | JSON | no |  |  |
| `trigger_evidence_json` | JSON | no |  |  |
| `expected_effect_paise` | BIGINT | no | `0` | integer paise |
| `expected_effect_text` | TEXT | no | `` |  |
| `downside_text` | TEXT | no | `` |  |
| `required_action` | TEXT | no | `` |  |
| `deadline` | DATE | yes |  |  |
| `confidence` | FLOAT | no | `0.5` |  |
| `explanation` | TEXT | no | `` |  |
| `linked_scenario_id` | VARCHAR(32) | yes |  |  |
| `state_id` | VARCHAR(32) | yes |  |  |
| `status` | VARCHAR(20) | no | `open` |  |
| `requires_approval` | BOOLEAN | no | `True` |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_recommendations_business_id` (business_id), `ix_recommendations_code` (code)

### `copilot_messages`

`generator` records whether the prose came from the model or the deterministic renderer, and why.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `conversation_id` | VARCHAR(32) | no |  |  |
| `role` | VARCHAR(12) | no |  |  |
| `content` | TEXT | no | `` |  |
| `tool_calls_json` | JSON | no |  |  |
| `evidence_json` | JSON | no |  |  |
| `state_refs_json` | JSON | no |  |  |
| `language` | VARCHAR(8) | no | `en` |  |
| `generator` | VARCHAR(120) | no | `deterministic` |  |
| `created_at` | DATETIME | no |  |  |

Indexes: `ix_copilot_messages_business_id` (business_id), `ix_copilot_messages_conversation_id` (conversation_id)

### `twin_events`

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | INTEGER | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `at` | DATETIME | no |  |  |
| `kind` | VARCHAR(40) | no |  |  |
| `summary` | VARCHAR(300) | no |  |  |
| `state_id` | VARCHAR(32) | yes |  |  |
| `detail_json` | JSON | no |  |  |

Indexes: `ix_twin_events_at` (at), `ix_twin_events_business_id` (business_id)

### `shared_reports`

A consent-bound passport snapshot. Revocation disables the public link immediately.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | VARCHAR(32) | no |  | **PK** |
| `business_id` | VARCHAR(32) | no |  |  |
| `consent_id` | VARCHAR(32) | no |  |  |
| `token` | VARCHAR(64) | no |  |  |
| `recipient` | VARCHAR(200) | no | `` |  |
| `payload_json` | JSON | no |  |  |
| `expires_at` | DATETIME | yes |  |  |
| `revoked_at` | DATETIME | yes |  |  |
| `view_count` | INTEGER | no | `0` |  |
| `created_at` | DATETIME | no |  |  |
| `updated_at` | DATETIME | no |  |  |

Indexes: `ix_shared_reports_business_id` (business_id), `ix_shared_reports_token` (token)

---

## Relationships that matter

```
businesses ─┬─ memberships ── users
            ├─ accounts ──────── transactions ─┬─ allocations ── invoices
            ├─ counterparties ─────────────────┘                    │
            │        └──────────────────────────────────────────────┘
            ├─ obligations, loans
            ├─ business_states ─┬─ actual_snapshots
            │                   ├─ predicted_snapshots ─┬─ forecast_points
            │                   │                       └─ payment_predictions
            │                   └─ simulated_snapshots ── scenarios ── scenario_decisions
            ├─ alerts, recommendations, twin_events, copilot_messages
            └─ consents ── shared_reports
```

The `allocations` table is the hinge of the whole ledger: it is a many-to-many join
between transactions and invoices **carrying an amount**, which is what makes
partial payments, split settlements, gateway fees and refunds representable without
distorting either side.

## Query patterns

```sql
-- Open receivables as of a date (point-in-time, not "current")
SELECT * FROM invoices
WHERE business_id = ? AND kind = 'sales'
  AND issue_date <= :as_of
  AND (settled_date IS NULL OR settled_date > :as_of);

-- Transactions that need a human
SELECT * FROM transactions
WHERE business_id = ?
  AND (recon_status IN ('needs_review','duplicate_suspect')
       OR category_confidence < 0.55);

-- Forecast accuracy by horizon
SELECT horizon_weeks, COUNT(*) AS n,
       AVG(ABS(p50_paise - actual_paise)) AS mae,
       AVG(CASE WHEN actual_paise BETWEEN p10_paise AND p90_paise THEN 1.0 ELSE 0 END) AS coverage
FROM forecast_points
WHERE business_id = ? AND actual_paise IS NOT NULL
GROUP BY horizon_weeks ORDER BY horizon_weeks;
```
