"""Shared vocabulary for the financial engine.

These string enums are persisted as-is, so values are append-only.
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    MANAGER = "manager"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"


class MembershipStatus(StrEnum):
    PENDING = "pending"      # signed up, waiting for the required approvals
    APPROVED = "approved"    # may access the business
    REJECTED = "rejected"


class Industry(StrEnum):
    WHOLESALE = "wholesale_distribution"
    MANUFACTURING = "manufacturing"
    RETAIL = "retail"
    SERVICES = "services"


class AccountKind(StrEnum):
    CURRENT = "current"
    SAVINGS = "savings"
    CASH = "cash"
    OVERDRAFT = "overdraft"
    WALLET = "wallet"


class PartyType(StrEnum):
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    BOTH = "both"
    INTERNAL = "internal"
    STATUTORY = "statutory"
    EMPLOYEE = "employee"
    LENDER = "lender"


class Direction(StrEnum):
    CREDIT = "credit"   # money into the business
    DEBIT = "debit"     # money out of the business


class TxnCategory(StrEnum):
    CUSTOMER_RECEIPT = "customer_receipt"
    SUPPLIER_PAYMENT = "supplier_payment"
    PAYROLL = "payroll"
    GST_PAYMENT = "gst_payment"
    PF_ESI = "pf_esi"
    TAX_OTHER = "tax_other"
    RENT = "rent"
    UTILITIES = "utilities"
    FREIGHT = "freight"
    LOAN_DISBURSAL = "loan_disbursal"
    LOAN_REPAYMENT = "loan_repayment"
    BANK_CHARGES = "bank_charges"
    INTEREST_INCOME = "interest_income"
    GATEWAY_FEE = "gateway_fee"
    REFUND_OUT = "refund_out"
    REFUND_IN = "refund_in"
    OWNER_DRAW = "owner_draw"
    CAPITAL_IN = "capital_in"
    TRANSFER = "internal_transfer"
    OTHER_EXPENSE = "other_expense"
    OTHER_INCOME = "other_income"
    UNCATEGORISED = "uncategorised"


INFLOW_CATEGORIES = {
    TxnCategory.CUSTOMER_RECEIPT, TxnCategory.INTEREST_INCOME,
    TxnCategory.REFUND_IN, TxnCategory.LOAN_DISBURSAL,
    TxnCategory.CAPITAL_IN, TxnCategory.OTHER_INCOME,
}


class Evidence(StrEnum):
    """The evidence hierarchy mandated by Anchor 03 §11.

    A value may be *demoted* freely but is only ever *promoted* by an
    explicit, audited action (see ``app.financial_states.provenance``).
    """
    VERIFIED_ACTUAL = "verified_actual"            # 1 - reconciled against a source document
    IMPORTED_ACTUAL = "imported_actual"            # 2 - from a feed, not yet verified
    OWNER_ESTIMATE = "owner_estimate"              # 3 - typed in by a human
    MODEL_PREDICTION = "model_prediction"          # 4 - produced by a forecaster
    SCENARIO_ASSUMPTION = "scenario_assumption"    # 5 - a what-if input
    SIMULATION_OUTPUT = "simulation_output"        # 6 - computed from (5)


EVIDENCE_RANK = {
    Evidence.VERIFIED_ACTUAL: 1, Evidence.IMPORTED_ACTUAL: 2,
    Evidence.OWNER_ESTIMATE: 3, Evidence.MODEL_PREDICTION: 4,
    Evidence.SCENARIO_ASSUMPTION: 5, Evidence.SIMULATION_OUTPUT: 6,
}
ACTUAL_EVIDENCE = {Evidence.VERIFIED_ACTUAL, Evidence.IMPORTED_ACTUAL}


class ReconStatus(StrEnum):
    UNRECONCILED = "unreconciled"
    PARTIALLY_MATCHED = "partially_matched"
    MATCHED = "matched"
    NEEDS_REVIEW = "needs_review"
    IGNORED = "ignored"
    DUPLICATE_SUSPECT = "duplicate_suspect"


class InvoiceKind(StrEnum):
    SALES = "sales"        # receivable
    PURCHASE = "purchase"  # payable


class InvoiceStatus(StrEnum):
    OPEN = "open"
    PART_PAID = "part_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    WRITTEN_OFF = "written_off"
    CANCELLED = "cancelled"


class ObligationKind(StrEnum):
    GST = "gst"
    TDS = "tds"
    PAYROLL = "payroll"
    PF_ESI = "pf_esi"
    RENT = "rent"
    LOAN_EMI = "loan_emi"
    SUPPLIER = "supplier"
    UTILITY = "utility"
    INSURANCE = "insurance"
    OTHER = "other"


class StateType(StrEnum):
    ACTUAL = "actual"
    PREDICTED = "predicted"
    SIMULATED = "simulated"


class AlertLevel(StrEnum):
    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


ALERT_RANK = {AlertLevel.INFO: 0, AlertLevel.WATCH: 1, AlertLevel.WARNING: 2, AlertLevel.CRITICAL: 3}


class ScenarioKind(StrEnum):
    NEW_ORDER = "new_order"
    PAYMENT_DELAY = "payment_delay"
    REVENUE_SHOCK = "revenue_shock"
    COST_INCREASE = "cost_increase"
    HIRING = "hiring"
    EQUIPMENT_PURCHASE = "equipment_purchase"
    FINANCING = "financing"
    INVOICE_DISCOUNTING = "invoice_discounting"
    SUPPLIER_TERMS = "supplier_terms"
    DEFER_PURCHASE = "defer_purchase"
    CUSTOMER_DEFAULT = "customer_default"
    ONE_OFF_EXPENSE = "one_off_expense"
    COMPOSITE = "composite"


class DecisionStatus(StrEnum):
    DRAFT = "draft"
    CONSIDERING = "considering"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class IntegrationStatus(StrEnum):
    AVAILABLE = "available"            # works right now with no credentials
    SANDBOX_REQUIRED = "sandbox_required"
    PARTNER_REQUIRED = "partner_required"
    REGULATED_ENTITY_REQUIRED = "regulated_entity_required"
    PLANNED = "planned"
