# Security and privacy

Financial data is the most sensitive data a small business has. This document states
what is implemented, what is deliberately out of scope for this build, and what a
production deployment would still require.

---

## Implemented

### Authentication
- **PBKDF2-HMAC-SHA256**, 240,000 iterations, 16-byte random salt per password,
  constant-time comparison. Accepted under NIST SP 800-63B.
- Signed **JWT** bearer tokens, 12-hour expiry, issuer-checked, HS256.
- Login failures are **indistinguishable** between a wrong password and a
  non-existent account — the hash is computed either way so the response time does
  not leak account existence. Asserted by
  `test_a_missing_account_is_indistinguishable_from_a_wrong_password`.

### Authorisation
- Four roles with a power ordering: `viewer` < `accountant` < `manager` < `owner`.
- Every mutating endpoint declares its minimum role.
- Role is resolved from the caller's **membership**, never from the request body.

### Tenant isolation
- Every tenant-scoped table carries `business_id`.
- Every request resolves a `TenantContext` from the membership table. A business id
  supplied by the client that the caller has no membership in returns **403**, not
  an empty result.
- **No copilot tool accepts a business id.** Tools receive a bundle built for
  exactly one business, so there is no parameter through which data could cross
  tenants even if a model were persuaded to try.
- Asserted by `test_a_user_cannot_read_a_business_they_do_not_belong_to` and
  `test_tool_schema_exposes_no_business_parameter`.

### Consent
- `consents` records a purpose, a scope, a grantee, a grant time and an expiry.
- Every shared Cash Health Passport is bound to a consent and can be revoked.
  Revocation takes effect immediately — the public link returns **410 Gone**.
- Asserted by `test_a_shared_report_link_can_be_revoked`.

### Prompt-injection defence
The copilot reads bank narrations, uploaded documents and counterparty names. All
three are attacker-controllable in a real deployment.

1. **Routing never sees untrusted text.** Tool selection is deterministic pattern
   matching on the user's own question, before any model call. Narration content
   cannot steer which financial tool runs.
2. **Fencing.** Every untrusted string is wrapped in `<untrusted_data>` and the
   system prompt declares that content inside the fence is data and must never be
   followed as an instruction. Fence-escape attempts are neutralised.
3. **Numeric verification.** Every rupee figure in a model reply is checked against
   the tool payload. A figure the tools did not produce causes the reply to be
   **discarded** and the deterministic renderer used instead, with the reason
   recorded in the message's `generator` field.
4. **No tool execution by the model.** The model receives results; it never chooses
   or invokes a tool.

Asserted by `test_untrusted_text_is_fenced`, `test_a_fence_cannot_be_escaped`,
`test_a_figure_the_tools_did_not_produce_is_rejected`,
`test_injection_in_a_narration_cannot_change_routing`.

### Input validation
- Pydantic models on every request body, with bounds on every numeric field.
- Upload size capped at 12 MB; empty uploads rejected.
- Enumerations validated against their declared values.
- Every parameterised query goes through SQLAlchemy; no string-built SQL exists.

### Rate limiting
- Sliding-window counter, 240 requests per minute per client IP on `/api/*`.
- A separate, stricter counter on login, keyed by IP.
- A separate counter on the copilot, keyed by user.

### Audit logging
- `audit_log` records actor, action, entity, detail and IP for every mutation.
- `twin_events` records every state rebuild, forecast run and scenario.
- `transform_log_json` on every transaction records every transformation,
  including owner corrections.

### Data minimisation
- **No bank credentials are stored anywhere.** The importers read files; they do not
  authenticate to anything.
- No card numbers, no PANs, no Aadhaar.
- Account numbers are stored **masked** (`XXXX4417`).
- The user's email appears only on their own account record.

### Transport and headers
- CORS restricted to configured origins.
- Every response carries a request id and a timing header.
- Unhandled exceptions return a generic message plus the request id — no stack
  trace, no internal path.

---

## Deliberately out of scope for this build

These are **not** implemented, and the product does not imply otherwise.

| Not implemented | What it would take |
|---|---|
| **Encryption at rest** | SQLite with SQLCipher, or PostgreSQL with pgcrypto / transparent disk encryption plus a KMS. The field-level design (which columns, which keys) is the real work. |
| **TLS** | Terminated at a reverse proxy in any real deployment. Not configured here. |
| **Secrets management** | `RUNWAY_SECRET_KEY` has an insecure default and is read from the environment. Production needs a vault and rotation. |
| **Refresh tokens / revocation list** | Tokens are stateless and valid until expiry. There is no server-side revocation. |
| **MFA** | Not implemented. Required before any real financial data. |
| **Distributed rate limiting** | The counter is in-process. A second instance doubles the effective limit. |
| **Backup and recovery** | No scheduled backup, no tested restore. |
| **Data deletion workflow** | DPDP Act erasure rights need a defined, auditable deletion path with retention carve-outs for statutory records. The `consents` table is the foundation; the workflow is not built. |
| **Penetration testing** | None performed. |

---

## Known weaknesses in the current build

1. **`RUNWAY_SECRET_KEY` has a committed default.** Anyone who runs the project
   unchanged can forge a token. Acceptable for a local demo; catastrophic
   otherwise. The `.env.example` says so in capitals.
2. **Demo accounts have published passwords.** By design, documented, and they exist
   only in the demo workspace.
3. **`create_all()` instead of migrations.** No schema versioning. Alembic is the
   first item on the production list.
4. **Single-process limiter and cache.** Correct for one instance only.
5. **No CSP or security headers.** Next.js defaults only.
6. **The LLM path sends tool output to a third party** when a key is configured.
   That output contains financial figures. Without a key nothing leaves the machine,
   and the product is fully functional that way — which is the default.

---

## Threat model

| Threat | Handling |
|---|---|
| Credential stuffing | Rate-limited login, strong hashing, uniform error responses |
| Token theft | Short expiry; HTTPS assumed in deployment; no revocation list (gap) |
| Horizontal privilege escalation | Membership-resolved tenancy, 403 on foreign business ids, tools that cannot take a business id |
| Vertical privilege escalation | Role power ordering checked per mutating endpoint |
| SQL injection | Parameterised ORM throughout |
| Prompt injection | Deterministic routing, fencing, numeric verification, no model-driven tool execution |
| Malicious upload | Size cap, type-specific parsers, per-row error isolation, dry-run preview before any write |
| Data exfiltration via a shared report | Consent-bound, expiring, revocable, view-counted |
| Accidental disclosure in logs | Structured logging of method, path, status and timing — never bodies |

---

## For a production deployment

In order:

1. Replace `RUNWAY_SECRET_KEY` from a secrets manager; rotate on a schedule.
2. Move to PostgreSQL with Alembic migrations and encryption at rest.
3. Terminate TLS at a proxy; add HSTS, CSP, `X-Content-Type-Options`, `Referrer-Policy`.
4. Add MFA for owner accounts.
5. Move rate limiting and caching to a shared store.
6. Replace PBKDF2 with argon2id.
7. Add refresh tokens with server-side revocation.
8. Build the DPDP erasure workflow with statutory retention carve-outs.
9. Scheduled encrypted backups with a tested restore.
10. Independent penetration test before any real financial data is accepted.

---

## Privacy position

- The business owns its data. The Cash Health Passport is the business's record,
  issued under its consent, revocable at any time.
- **RUNWAY does not sell or syndicate financial data.** Stated in the product, in
  the shared report, and here.
- Any future benchmarking must be consented and privacy-preserving — a differential
  or k-anonymous aggregate, never a cross-tenant join. It is not built, and it is
  listed in `ROADMAP.md` as a privacy design problem before it is an engineering one.
- Purpose limitation is modelled explicitly: a consent carries a purpose and a scope,
  not a blanket grant.
