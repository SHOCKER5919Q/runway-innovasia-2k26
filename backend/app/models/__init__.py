"""SQLAlchemy 2.0 ORM models for RUNWAY.

Conventions
-----------
* Every monetary column is ``BigInteger`` **paise** (see ``app.core.money``).
* Every tenant-scoped table carries ``business_id`` and is filtered through
  ``app.api.deps.tenant_scope`` - never queried without it.
* ``evidence`` columns implement the Anchor-03 evidence hierarchy.
* JSON blobs are used for genuinely open-ended metadata only; anything that
  is queried or joined gets a real column.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.enums import (
    AccountKind, AlertLevel, DecisionStatus, Direction, Evidence, Industry,
    InvoiceKind, InvoiceStatus, ObligationKind, PartyType, ReconStatus, Role,
    ScenarioKind, StateType, TxnCategory,
)


def _uid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# ─────────────────────────────── tenancy ────────────────────────────────

class Business(Base, TimestampMixin):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(40), default=Industry.WHOLESALE)
    gstin: Mapped[str | None] = mapped_column(String(15))
    city: Mapped[str | None] = mapped_column(String(80))
    state_code: Mapped[str | None] = mapped_column(String(4))
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=4)  # April, India
    # MSMED classification of *this* business (affects 43B(h) as a seller)
    msme_class: Mapped[str] = mapped_column(String(10), default="small")  # micro|small|medium|none
    udyam_number: Mapped[str | None] = mapped_column(String(32))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    demo_scenario: Mapped[str | None] = mapped_column(String(40))
    # policy
    safety_buffer_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    target_runway_weeks: Mapped[float] = mapped_column(Float, default=8.0)
    max_customer_concentration: Mapped[float] = mapped_column(Float, default=0.35)
    max_borrowing_apr: Mapped[float] = mapped_column(Float, default=0.24)
    min_order_margin: Mapped[float] = mapped_column(Float, default=0.10)
    risk_appetite: Mapped[str] = mapped_column(String(16), default="balanced")  # conservative|balanced|aggressive
    locale: Mapped[str] = mapped_column(String(8), default="en-IN")
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="business", cascade="all, delete-orphan")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_accountant: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_language: Mapped[str] = mapped_column(String(8), default="en")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "business_id", name="uq_membership"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), default=Role.OWNER)
    # purpose-limited scopes, e.g. ["read:ledger","read:forecast"]
    scopes_json: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped[User] = relationship(back_populates="memberships")
    business: Mapped[Business] = relationship(back_populates="memberships")


class Consent(Base, TimestampMixin):
    """Explicit, revocable permission - AA consent, report sharing, etc."""
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(120))         # aa_fetch | share_passport | accountant_access
    scope_json: Mapped[list] = mapped_column(JSON, default=list)
    granted_by_user_id: Mapped[str | None] = mapped_column(String(32))
    grantee: Mapped[str | None] = mapped_column(String(200))  # bank / NBFC / CA name
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token: Mapped[str] = mapped_column(String(64), default=_uid, index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    business_id: Mapped[str | None] = mapped_column(String(32), index=True)
    user_id: Mapped[str | None] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64))


# ───────────────────────── ledger & master data ──────────────────────────

class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(20), default=AccountKind.CURRENT)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    masked_number: Mapped[str | None] = mapped_column(String(40))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    opening_balance_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    opening_date: Mapped[date] = mapped_column(Date)
    # Overdraft / CC limits are *available* liquidity, not cash. Kept apart.
    overdraft_limit_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    # Lien-marked / FD-pledged balances that cannot fund operations.
    restricted_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_system: Mapped[str] = mapped_column(String(40), default="manual")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparties"
    __table_args__ = (Index("ix_cp_business_name", "business_id", "name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    normalised_name: Mapped[str] = mapped_column(String(200), index=True)
    party_type: Mapped[str] = mapped_column(String(20), default=PartyType.CUSTOMER)
    gstin: Mapped[str | None] = mapped_column(String(15), index=True)
    sector: Mapped[str | None] = mapped_column(String(60))
    region: Mapped[str | None] = mapped_column(String(60))
    # Counterparty's own MSMED class: drives 43B(h) when they are our supplier.
    msme_class: Mapped[str | None] = mapped_column(String(10))
    credit_days: Mapped[int] = mapped_column(Integer, default=30)
    credit_limit_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    early_payment_discount_pct: Mapped[float] = mapped_column(Float, default=0.0)
    early_payment_days: Mapped[int] = mapped_column(Integer, default=0)
    contact_name: Mapped[str | None] = mapped_column(String(120))
    contact_phone: Mapped[str | None] = mapped_column(String(20))
    contact_email: Mapped[str | None] = mapped_column(String(160))
    aliases_json: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    adapter: Mapped[str] = mapped_column(String(60))
    filename: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    rows_seen: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[list] = mapped_column(JSON, default=list)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Transaction(Base, TimestampMixin):
    """One canonical movement of money. Source rows are preserved verbatim
    in ``raw_json`` and the normalisation steps in ``transform_log_json``."""
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_txn_business_date", "business_id", "value_date"),
        Index("ix_txn_business_recon", "business_id", "recon_status"),
        Index("ix_txn_fingerprint", "business_id", "fingerprint"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    counterparty_id: Mapped[str | None] = mapped_column(ForeignKey("counterparties.id", ondelete="SET NULL"))
    import_batch_id: Mapped[str | None] = mapped_column(String(32), index=True)

    source_system: Mapped[str] = mapped_column(String(60), default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(120))
    value_date: Mapped[date] = mapped_column(Date, nullable=False)   # when cash moved
    posting_date: Mapped[date | None] = mapped_column(Date)          # when the bank booked it
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)  # always positive
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    narration: Mapped[str] = mapped_column(Text, default="")
    reference_no: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(40), default=TxnCategory.UNCATEGORISED, index=True)
    category_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # Holds the classifier rule label (longest today: 25 chars). Sized with
    # headroom because a new rule must never fail an insert.
    category_source: Mapped[str] = mapped_column(String(60), default="rules")
    evidence: Mapped[str] = mapped_column(String(24), default=Evidence.IMPORTED_ACTUAL)
    recon_status: Mapped[str] = mapped_column(String(24), default=ReconStatus.UNRECONCILED)
    allocated_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    # Gateway settlements: gross = net + fee; all three retained.
    gross_paise: Mapped[int | None] = mapped_column(BigInteger)
    fee_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    is_reversal_of: Mapped[str | None] = mapped_column(String(32))
    fingerprint: Mapped[str] = mapped_column(String(64), default="")
    duplicate_of: Mapped[str | None] = mapped_column(String(32))
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    transform_log_json: Mapped[list] = mapped_column(JSON, default=list)

    @property
    def signed_paise(self) -> int:
        return self.amount_paise if self.direction == Direction.CREDIT else -self.amount_paise

    @property
    def settleable_paise(self) -> int:
        """How much invoice value this transaction can settle.

        For a payment-gateway settlement the customer paid the **gross**; the
        gateway kept the fee and only the net reached the bank. Crediting the
        invoice with the net would leave it permanently short by the MDR, so
        the settleable amount is the gross where one is recorded.
        """
        return self.gross_paise or self.amount_paise

    @property
    def unallocated_paise(self) -> int:
        return max(0, self.settleable_paise - self.allocated_paise)


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_inv_business_due", "business_id", "due_date"),
        Index("ix_inv_business_kind_status", "business_id", "kind", "status"),
        UniqueConstraint("business_id", "kind", "invoice_no", name="uq_invoice_no"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    counterparty_id: Mapped[str] = mapped_column(ForeignKey("counterparties.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default=InvoiceKind.SALES)
    invoice_no: Mapped[str] = mapped_column(String(60))
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    credit_days: Mapped[int] = mapped_column(Integer, default=30)
    taxable_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    settled_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    written_off_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(16), default=InvoiceStatus.OPEN, index=True)
    gst_rate: Mapped[float] = mapped_column(Float, default=0.18)
    place_of_supply: Mapped[str | None] = mapped_column(String(4))
    has_written_agreement: Mapped[bool] = mapped_column(Boolean, default=True)
    source_system: Mapped[str] = mapped_column(String(40), default="manual")
    evidence: Mapped[str] = mapped_column(String(24), default=Evidence.IMPORTED_ACTUAL)
    first_payment_date: Mapped[date | None] = mapped_column(Date)
    settled_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)

    @property
    def outstanding_paise(self) -> int:
        return max(0, self.total_paise - self.settled_paise - self.written_off_paise)


class Allocation(Base, TimestampMixin):
    """Links a bank transaction to an invoice. Partial payments, split
    settlements and refunds are all expressed as multiple allocations."""
    __tablename__ = "allocations"
    __table_args__ = (
        Index("ix_alloc_txn", "transaction_id"),
        Index("ix_alloc_inv", "invoice_id"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"))
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(24), default="auto")  # auto|manual|exact_ref|amount_date
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    rationale: Mapped[str] = mapped_column(String(300), default="")
    confirmed_by_user_id: Mapped[str | None] = mapped_column(String(32))


class Obligation(Base, TimestampMixin):
    """A known or estimated future outflow that is not a supplier invoice."""
    __tablename__ = "obligations"
    __table_args__ = (Index("ix_oblig_business_due", "business_id", "due_date"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default=ObligationKind.OTHER)
    label: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    evidence: Mapped[str] = mapped_column(String(24), default=Evidence.OWNER_ESTIMATE)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence: Mapped[str | None] = mapped_column(String(20))  # monthly|quarterly|weekly
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_transaction_id: Mapped[str | None] = mapped_column(String(32))
    reserve_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    counterparty_id: Mapped[str | None] = mapped_column(String(32))
    source_system: Mapped[str] = mapped_column(String(40), default="derived")
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Loan(Base, TimestampMixin):
    __tablename__ = "loans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    lender: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(30), default="term")  # term|working_capital|od|invoice_discounting
    principal_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    outstanding_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    annual_rate: Mapped[float] = mapped_column(Float, default=0.14)
    emi_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    emi_day: Mapped[int] = mapped_column(Integer, default=5)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ─────────────────────── three-state architecture ────────────────────────

class BusinessState(Base):
    """Immutable, versioned header for every actual/predicted/simulated state."""
    __tablename__ = "business_states"
    __table_args__ = (
        Index("ix_state_lookup", "business_id", "state_type", "version"),
        UniqueConstraint("business_id", "state_type", "version", name="uq_state_version"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    state_type: Mapped[str] = mapped_column(String(12), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    source_state_id: Mapped[str | None] = mapped_column(String(32))  # parent lineage
    engine_version: Mapped[str] = mapped_column(String(20), default="0.9.0")
    ledger_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    data_quality_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="current")  # current|superseded
    trigger: Mapped[str] = mapped_column(String(80), default="manual")


class ActualSnapshot(Base):
    __tablename__ = "actual_snapshots"
    state_id: Mapped[str] = mapped_column(ForeignKey("business_states.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    cash_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    restricted_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    committed_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    available_liquidity_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    overdraft_headroom_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    receivables_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    receivables_overdue_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    payables_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    payables_overdue_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    loan_outstanding_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    revenue_30d_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    expense_30d_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    net_burn_weekly_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    working_capital_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


class PredictedSnapshot(Base):
    __tablename__ = "predicted_snapshots"
    state_id: Mapped[str] = mapped_column(ForeignKey("business_states.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    baseline_actual_state_id: Mapped[str] = mapped_column(String(32), index=True)
    # Composite of the delay model and the cash model, joined by "|".
    model_version: Mapped[str] = mapped_column(String(120), default="")
    horizon_weeks: Mapped[int] = mapped_column(Integer, default=13)
    method: Mapped[str] = mapped_column(String(120), default="ledger_driven_monte_carlo")
    seed: Mapped[int] = mapped_column(Integer, default=0)
    runway_weeks_p50: Mapped[float] = mapped_column(Float, default=0.0)
    runway_weeks_p10: Mapped[float] = mapped_column(Float, default=0.0)
    min_cash_p50_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    min_cash_p10_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    first_breach_week: Mapped[int | None] = mapped_column(Integer)
    breach_probability: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_var_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    liquidity_cvar_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    assumptions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    series_json: Mapped[dict] = mapped_column(JSON, default=dict)   # weekly P10/P50/P90 + drivers
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SimulatedSnapshot(Base):
    __tablename__ = "simulated_snapshots"
    state_id: Mapped[str] = mapped_column(ForeignKey("business_states.id", ondelete="CASCADE"), primary_key=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    scenario_id: Mapped[str] = mapped_column(String(32), index=True)
    baseline_actual_state_id: Mapped[str] = mapped_column(String(32))
    baseline_predicted_state_id: Mapped[str] = mapped_column(String(32))
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    runway_weeks_p50: Mapped[float] = mapped_column(Float, default=0.0)
    min_cash_p50_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    min_cash_p10_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    peak_wc_requirement_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    breach_probability: Mapped[float] = mapped_column(Float, default=0.0)
    expected_profit_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    financing_cost_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Scenario(Base, TimestampMixin):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32), default=ScenarioKind.COMPOSITE)
    description: Mapped[str] = mapped_column(Text, default="")
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline_actual_state_id: Mapped[str | None] = mapped_column(String(32))
    baseline_predicted_state_id: Mapped[str | None] = mapped_column(String(32))
    parent_scenario_id: Mapped[str | None] = mapped_column(String(32))
    created_by_user_id: Mapped[str | None] = mapped_column(String(32))
    origin: Mapped[str] = mapped_column(String(20), default="ui")  # ui|copilot|preset
    last_run_state_id: Mapped[str | None] = mapped_column(String(32))
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)


class ScenarioDecision(Base, TimestampMixin):
    __tablename__ = "scenario_decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DecisionStatus.DRAFT)
    decided_by_user_id: Mapped[str | None] = mapped_column(String(32))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    implementation_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    # Realised outcome, filled only from verified transactions.
    actual_refs_json: Mapped[list] = mapped_column(JSON, default=list)
    outcome_json: Mapped[dict] = mapped_column(JSON, default=dict)


class StateComparison(Base):
    __tablename__ = "state_comparisons"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    source_state_id: Mapped[str] = mapped_column(String(32))
    target_state_id: Mapped[str] = mapped_column(String(32))
    comparison_type: Mapped[str] = mapped_column(String(40))  # actual_vs_predicted | predicted_vs_simulated | simulated_vs_actual
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ForecastPoint(Base):
    """Flattened weekly forecast rows kept for backtesting against actuals."""
    __tablename__ = "forecast_points"
    __table_args__ = (Index("ix_fp_lookup", "business_id", "target_week_start", "predicted_state_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    predicted_state_id: Mapped[str] = mapped_column(String(32), index=True)
    created_on: Mapped[date] = mapped_column(Date)
    target_week_start: Mapped[date] = mapped_column(Date)
    horizon_weeks: Mapped[int] = mapped_column(Integer)
    metric: Mapped[str] = mapped_column(String(32), default="closing_cash")
    p10_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    p50_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    p90_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    actual_paise: Mapped[int | None] = mapped_column(BigInteger)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentPrediction(Base):
    """Invoice-level payment-date prediction, versioned per forecast run."""
    __tablename__ = "payment_predictions"
    __table_args__ = (Index("ix_pp_lookup", "business_id", "invoice_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    invoice_id: Mapped[str] = mapped_column(String(32), index=True)
    predicted_state_id: Mapped[str | None] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    model_version: Mapped[str] = mapped_column(String(120), default="")
    predicted_delay_days_p50: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_delay_days_p10: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_delay_days_p90: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_pay_date: Mapped[date] = mapped_column(Date)
    prob_within_7: Mapped[float] = mapped_column(Float, default=0.0)
    prob_within_15: Mapped[float] = mapped_column(Float, default=0.0)
    prob_within_30: Mapped[float] = mapped_column(Float, default=0.0)
    prob_default: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    drivers_json: Mapped[list] = mapped_column(JSON, default=list)   # SHAP-style contributions
    actual_delay_days: Mapped[float | None] = mapped_column(Float)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelRun(Base):
    __tablename__ = "model_runs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    model_name: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(120))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    n_train: Mapped[int] = mapped_column(Integer, default=0)
    n_test: Mapped[int] = mapped_column(Integer, default=0)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")


# ───────────────────── risk, advice & conversation ──────────────────────

class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alert_business_level", "business_id", "level", "is_open"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    level: Mapped[str] = mapped_column(String(12), default=AlertLevel.INFO)
    title: Mapped[str] = mapped_column(String(220))
    what_happened: Mapped[str] = mapped_column(Text, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    impact_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    impact_date: Mapped[date | None] = mapped_column(Date)
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    if_ignored: Mapped[str] = mapped_column(Text, default="")
    state_id: Mapped[str | None] = mapped_column(String(32))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    dedupe_key: Mapped[str] = mapped_column(String(120), default="", index=True)


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(220))
    priority: Mapped[int] = mapped_column(Integer, default=50)      # 0..100, higher first
    score_json: Mapped[dict] = mapped_column(JSON, default=dict)    # explainable ranking terms
    trigger_evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    expected_effect_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    expected_effect_text: Mapped[str] = mapped_column(Text, default="")
    downside_text: Mapped[str] = mapped_column(Text, default="")
    required_action: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    explanation: Mapped[str] = mapped_column(Text, default="")
    linked_scenario_id: Mapped[str | None] = mapped_column(String(32))
    state_id: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|accepted|dismissed|done
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    conversation_id: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user|assistant|tool
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls_json: Mapped[list] = mapped_column(JSON, default=list)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    state_refs_json: Mapped[dict] = mapped_column(JSON, default=dict)
    language: Mapped[str] = mapped_column(String(8), default="en")
    # "deterministic" | "llm" | "deterministic (<why the LLM reply was rejected>)".
    # The rejection reason is part of the value, so this is not a 20-char enum.
    generator: Mapped[str] = mapped_column(String(120), default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TwinEvent(Base):
    """Activity log of the digital twin: what changed and why."""
    __tablename__ = "twin_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(300))
    state_id: Mapped[str | None] = mapped_column(String(32))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SharedReport(Base, TimestampMixin):
    """Cash Health Passport issued under an explicit consent token."""
    __tablename__ = "shared_reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uid)
    business_id: Mapped[str] = mapped_column(String(32), index=True)
    consent_id: Mapped[str] = mapped_column(String(32))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_uid)
    recipient: Mapped[str] = mapped_column(String(200), default="")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_count: Mapped[int] = mapped_column(Integer, default=0)


__all__ = [n for n in dir() if n[0].isupper()]
