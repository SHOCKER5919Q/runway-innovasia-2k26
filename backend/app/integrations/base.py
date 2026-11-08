"""Integration adapter framework.

Every data source - a CSV today, an Account Aggregator tomorrow - implements
the same ``Adapter`` interface and returns ``NormalisedRow`` objects. Nothing
downstream knows or cares where a transaction came from, which is why adding
a provider never touches the ledger, the forecaster or the UI.

``status`` is deliberately part of the adapter declaration. RUNWAY states on
its own Integrations screen exactly what is working today and what would
require credentials, a partner or a regulated entity. Nothing is described
as live unless it has been exercised against a real endpoint.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from app.core.enums import Direction, Evidence, IntegrationStatus


@dataclass
class NormalisedRow:
    value_date: date
    amount_paise: int
    direction: str
    narration: str
    reference_no: str | None = None
    posting_date: date | None = None
    counterparty_hint: str | None = None
    invoice_ref: str | None = None
    gross_paise: int | None = None
    fee_paise: int = 0
    currency: str = "INR"
    evidence: str = Evidence.IMPORTED_ACTUAL
    raw: dict = field(default_factory=dict)


@dataclass
class ParseReport:
    rows_seen: int = 0
    rows_ok: int = 0
    rows_rejected: int = 0
    errors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    detected_format: str = ""
    column_mapping: dict = field(default_factory=dict)


class Adapter(abc.ABC):
    key: str
    label: str
    status: str = IntegrationStatus.AVAILABLE
    category: str = "bank"
    description: str = ""
    requirements: list[str] = []
    accepts: list[str] = [".csv"]
    produces: str = "transactions"   # transactions | invoices | obligations

    @abc.abstractmethod
    def parse(self, content: bytes, *, filename: str = "") -> tuple[list[Any], ParseReport]:
        ...

    def describe(self) -> dict:
        return {"key": self.key, "label": self.label, "status": self.status,
                "category": self.category, "description": self.description,
                "requirements": self.requirements, "accepts": self.accepts,
                "produces": self.produces}


REGISTRY: dict[str, Adapter] = {}


def register(cls: type[Adapter]) -> type[Adapter]:
    """Class decorator: instantiate once and put the instance in the registry."""
    REGISTRY[cls.key] = cls()
    return cls


# Declared-but-not-built connectors. They appear on the Integrations screen
# with an honest status so nobody mistakes the roadmap for the product.
PLANNED: list[dict] = [
    {"key": "account_aggregator", "label": "Account Aggregator (RBI / ReBIT)",
     "category": "banking", "status": IntegrationStatus.REGULATED_ENTITY_REQUIRED,
     "description": ("Consent-based bank data through the RBI Account Aggregator "
                     "framework, using the ReBIT FIU APIs."),
     "requirements": [
         "The platform operator must be a regulated entity (RBI / SEBI / IRDAI / PFRDA) "
         "eligible to register as a Financial Information User, or must work through "
         "one as a Technology Service Provider.",
         "An agreement with a licensed NBFC-AA.",
         "ReBIT client-standards adoption and a Sahamati ecosystem onboarding.",
         "Customer consent artefacts with purpose limitation and revocation."],
     "runway_support": ("The ingestion path is built and tested against ReBIT-shaped "
                        "sample payloads. Flip the adapter on once an FIU arrangement "
                        "exists. RUNWAY makes no claim of live AA connectivity."),
     "evidence": "docs/COMPLIANCE_NOTES.md"},
    {"key": "gst_gsp", "label": "GST returns via a GSP",
     "category": "compliance", "status": IntegrationStatus.PARTNER_REQUIRED,
     "description": "GSTR-1 / GSTR-2B / GSTR-3B pull through a GST Suvidha Provider.",
     "requirements": ["A GSP contract and API credentials",
                      "Taxpayer OTP or API-key authentication per GSTIN",
                      "Rate limits and reconciliation rules per return type"],
     "runway_support": ("JSON and CSV importers for the same return shapes are "
                        "available today, so the data model is already correct.")},
    {"key": "razorpay_webhook", "label": "Payment gateway settlements (webhook)",
     "category": "payments", "status": IntegrationStatus.SANDBOX_REQUIRED,
     "description": "Settlement webhooks with gross, fee and net amounts.",
     "requirements": ["Merchant account and webhook secret",
                      "Public HTTPS endpoint with signature verification"],
     "runway_support": ("The settlement CSV importer already splits gross, MDR and net "
                        "correctly, which is the part most tools get wrong.")},
    {"key": "tally_connector", "label": "TallyPrime live connector",
     "category": "accounting", "status": IntegrationStatus.SANDBOX_REQUIRED,
     "description": "Continuous sync over Tally's ODBC / XML gateway on the local network.",
     "requirements": ["Tally running with the XML gateway enabled",
                      "A local agent on the same network"],
     "runway_support": "Tally XML export files import today."},
    {"key": "whatsapp_briefing", "label": "WhatsApp daily briefing",
     "category": "messaging", "status": IntegrationStatus.PARTNER_REQUIRED,
     "description": "The morning briefing delivered to the owner on WhatsApp.",
     "requirements": ["WhatsApp Business Cloud API access",
                      "Message templates approved by Meta",
                      "A verified business phone number"],
     "runway_support": "The briefing is generated server-side and is already renderable as text."},
    {"key": "treds", "label": "TReDS invoice discounting",
     "category": "finance", "status": IntegrationStatus.PARTNER_REQUIRED,
     "description": "Bill discounting on an RBI-licensed TReDS exchange.",
     "requirements": ["Seller onboarding on a TReDS platform",
                      "Buyer acceptance of each invoice",
                      "A platform API agreement"],
     "runway_support": ("The discounting scenario models cost and net advance so the "
                        "decision can be evaluated before onboarding.")},
]
