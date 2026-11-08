"""Transaction categorisation.

A transparent rule engine, not a black box: every category carries the rule
that produced it and a confidence, and anything below ``REVIEW_THRESHOLD`` is
surfaced to the owner instead of being quietly accepted.

Rules are ordered; the first match wins, except that counterparty-type
evidence can override a generic match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.enums import Direction, PartyType, TxnCategory

REVIEW_THRESHOLD = 0.55


@dataclass(frozen=True)
class Rule:
    category: TxnCategory
    pattern: re.Pattern
    direction: str | None
    confidence: float
    label: str


def _r(cat, pat, direction, conf, label):
    return Rule(cat, re.compile(pat, re.I), direction, conf, label)


RULES: list[Rule] = [
    _r(TxnCategory.GST_PAYMENT, r"\b(gst|cgst|sgst|igst|gstn|pmt[-_ ]?06|gstr[- ]?3b)", Direction.DEBIT, 0.95, "GST keyword"),
    _r(TxnCategory.TAX_OTHER, r"\b(tds|tcs|advance tax|income tax|itns|professional tax|ptax)", Direction.DEBIT, 0.9, "Tax keyword"),
    _r(TxnCategory.PAYROLL, r"\b(salary|salaries|payroll|wages|stipend|staff sal)", Direction.DEBIT, 0.93, "Payroll keyword"),
    _r(TxnCategory.PF_ESI, r"\b(epfo|pf contrib|esic?)", Direction.DEBIT, 0.9, "PF/ESI keyword"),
    _r(TxnCategory.RENT, r"\b(rent|lease|godown rent|warehouse rent)", Direction.DEBIT, 0.88, "Rent keyword"),
    _r(TxnCategory.UTILITIES, r"\b(electricity|tneb|bescom|tgspdcl|power bill|water bill|broadband|internet|telephone|mobile bill)", Direction.DEBIT, 0.88, "Utility keyword"),
    _r(TxnCategory.FREIGHT, r"\b(freight|transport|logistics|courier|lorry|truck hire|cartage)", Direction.DEBIT, 0.82, "Freight keyword"),
    _r(TxnCategory.LOAN_REPAYMENT, r"\b(emi|loan repay|loan instal|principal\+int|term loan)", Direction.DEBIT, 0.9, "Loan EMI keyword"),
    _r(TxnCategory.LOAN_DISBURSAL, r"\b(loan disb|disbursal|od limit|cc limit|working capital loan)", Direction.CREDIT, 0.88, "Loan disbursal keyword"),
    _r(TxnCategory.BANK_CHARGES, r"\b(bank charge|service charge|sms charge|annual fee|neft charge|rtgs charge|gst on charge|folio)", Direction.DEBIT, 0.9, "Bank charge keyword"),
    _r(TxnCategory.INTEREST_INCOME, r"\b(interest credit|int\.? cr|fd interest|savings interest)", Direction.CREDIT, 0.9, "Interest keyword"),
    _r(TxnCategory.GATEWAY_FEE, r"\b(razorpay fee|pg fee|mdr|gateway charge|settlement fee)", Direction.DEBIT, 0.9, "Gateway fee keyword"),
    _r(TxnCategory.REFUND_OUT, r"\b(refund|reversal|returned goods|credit note)", Direction.DEBIT, 0.75, "Refund-out keyword"),
    _r(TxnCategory.REFUND_IN, r"\b(refund|reversal|debit note)", Direction.CREDIT, 0.7, "Refund-in keyword"),
    _r(TxnCategory.OWNER_DRAW, r"\b(drawings|owner withdraw|self transfer out|prop drawings)", Direction.DEBIT, 0.8, "Owner drawing keyword"),
    _r(TxnCategory.CAPITAL_IN, r"\b(capital introduced|owner contribution|equity infusion)", Direction.CREDIT, 0.85, "Capital keyword"),
    _r(TxnCategory.TRANSFER, r"\b(own account|self transfer|internal transfer|sweep)", None, 0.8, "Internal transfer keyword"),
    _r(TxnCategory.CUSTOMER_RECEIPT, r"\b(upi|neft|imps|rtgs|settlement|collection|received from|sale proceeds|invoice)", Direction.CREDIT, 0.45, "Generic inbound payment"),
    _r(TxnCategory.SUPPLIER_PAYMENT, r"\b(purchase|supplier|vendor|material|paid to|po\b|bill payment)", Direction.DEBIT, 0.5, "Generic outbound payment"),
]


def classify(narration: str, direction: str, *, counterparty_type: str | None = None,
             matched_invoice_kind: str | None = None) -> tuple[str, float, str]:
    """Return ``(category, confidence, rule_label)``.

    Hard evidence wins: if the transaction is already matched to a sales
    invoice it is a customer receipt regardless of what the narration says.
    """
    if matched_invoice_kind == "sales":
        return TxnCategory.CUSTOMER_RECEIPT, 0.99, "matched to sales invoice"
    if matched_invoice_kind == "purchase":
        return TxnCategory.SUPPLIER_PAYMENT, 0.99, "matched to purchase invoice"

    for rule in RULES:
        if rule.direction and rule.direction != direction:
            continue
        if rule.pattern.search(narration or ""):
            conf = rule.confidence
            # Counterparty master data corroborates a generic match.
            if counterparty_type == PartyType.CUSTOMER and rule.category == TxnCategory.CUSTOMER_RECEIPT:
                conf = min(0.92, conf + 0.25)
            if counterparty_type == PartyType.SUPPLIER and rule.category == TxnCategory.SUPPLIER_PAYMENT:
                conf = min(0.92, conf + 0.25)
            return rule.category, conf, rule.label

    if counterparty_type == PartyType.CUSTOMER and direction == Direction.CREDIT:
        return TxnCategory.CUSTOMER_RECEIPT, 0.7, "known customer, inbound"
    if counterparty_type == PartyType.SUPPLIER and direction == Direction.DEBIT:
        return TxnCategory.SUPPLIER_PAYMENT, 0.7, "known supplier, outbound"
    fallback = TxnCategory.OTHER_INCOME if direction == Direction.CREDIT else TxnCategory.OTHER_EXPENSE
    return fallback, 0.3, "no rule matched - needs review"
