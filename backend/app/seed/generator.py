"""Reproducible synthetic MSME generator.

Guarantees that the rest of the system depends on:

1. **It reconciles.** ``opening_balance + credits - debits == closing_balance``
   for every account, and every settled invoice is backed by allocations whose
   amounts sum exactly to the settled figure.
2. **It is reproducible.** One numpy ``Generator`` seeded from
   ``(seed, scenario)`` drives every random draw.
3. **It is labelled.** Every row is written with ``source_system='synthetic'``
   and the business carries ``is_demo=True``; nothing here can be mistaken for
   a real financial record.
4. **It is learnable.** Customer payment behaviour is drawn from stable
   per-customer distributions, so the payment-delay model has real signal to
   find rather than noise.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.core.enums import (
    AccountKind, Direction, Evidence, Industry, InvoiceKind, InvoiceStatus,
    ObligationKind, PartyType, ReconStatus, TxnCategory,
)
from app.core.money import rupees_to_paise, split_proportionally
from app.ledger.normalise import fingerprint, party_key
from app.models import (
    Account, Allocation, Business, Counterparty, Invoice, Loan, Obligation,
    Transaction, _uid,
)
from app.seed.profiles import SCENARIOS, DemoScenario, IndustryProfile, get_profile

HISTORY_DAYS = 540          # ~18 months, enough for seasonality + backtesting
FORWARD_INVOICE_DAYS = 75   # open invoices extending past "today"


# ───────────────────────────── master data ──────────────────────────────

@dataclass
class CustomerSpec:
    name: str
    sector: str
    region: str
    share: float              # share of revenue
    credit_days: int
    delay_mean: float         # mean days late vs due date
    delay_sd: float
    reliability: float        # P(pays without needing a reminder)
    partial_rate: float       # P(pays in two instalments)
    default_rate: float = 0.0
    drift_per_month: float = 0.0   # days added to the mean delay each month


WHOLESALE_CUSTOMERS = [
    CustomerSpec("ABC Distributors", "FMCG retail", "Hyderabad", 0.30, 45, 8.0, 7.5, 0.72, 0.28, drift_per_month=0.55),
    CustomerSpec("Venkata Traders", "General trade", "Vijayawada", 0.21, 30, 4.0, 4.0, 0.93, 0.08),
    CustomerSpec("Sri Balaji Agencies", "Pharma distribution", "Hyderabad", 0.18, 45, 9.0, 6.0, 0.85, 0.15),
    CustomerSpec("Nandi Retail Mart", "Modern retail", "Bengaluru", 0.16, 60, 7.0, 9.0, 0.80, 0.22, drift_per_month=0.30),
    CustomerSpec("Kakatiya Stores", "Kirana chain", "Warangal", 0.09, 21, 2.0, 3.0, 0.95, 0.05),
    CustomerSpec("Deccan Super Bazaar", "Supermarket", "Secunderabad", 0.06, 30, 6.0, 5.0, 0.88, 0.10),
]

WHOLESALE_SUPPLIERS = [
    ("XYZ Foods Pvt Ltd", "Packaged foods", 0.26, 30, "small", 0.0, 0),
    ("Krishna Oil Mills", "Edible oil", 0.18, 21, "small", 0.02, 10),
    ("Godavari Packaging", "Packaging", 0.11, 45, "micro", 0.0, 0),
    ("Telangana Agro Supplies", "Agri commodities", 0.14, 30, "small", 0.015, 7),
    ("Surya Beverages", "Beverages", 0.09, 15, "medium", 0.0, 0),
    ("Konark Detergents", "Home care", 0.07, 30, "small", 0.0, 0),
    ("Nagarjuna Spices", "Spices", 0.05, 45, "micro", 0.025, 10),
    ("Bharat Paper Products", "Stationery", 0.04, 30, "micro", 0.0, 0),
    ("Charminar Logistics", "Freight", 0.04, 15, "small", 0.0, 0),
    ("Prime Cold Storage", "Warehousing", 0.02, 30, "medium", 0.0, 0),
]


def _stable_seed(seed: int, scenario: str, business_name: str) -> int:
    h = hashlib.sha256(f"{seed}|{scenario}|{business_name}".encode()).hexdigest()
    return int(h[:8], 16)


@dataclass
class GeneratedLedger:
    business: Business
    accounts: list[Account]
    counterparties: list[Counterparty]
    invoices: list[Invoice]
    transactions: list[Transaction]
    allocations: list[Allocation]
    obligations: list[Obligation]
    loans: list[Loan]
    report: dict


class SyntheticBusinessGenerator:
    def __init__(self, *, today: date, scenario_key: str = "B", seed: int = 20260101,
                 industry: str = Industry.WHOLESALE,
                 business_name: str = "Sri Lakshmi Industrial Supplies",
                 annual_revenue_rupees: float = 4_80_00_000):
        self.today = today
        self.scenario: DemoScenario = SCENARIOS[scenario_key]
        self.profile: IndustryProfile = get_profile(industry)
        self.industry = industry
        self.business_name = business_name
        self.annual_revenue = annual_revenue_rupees
        self.seed = seed
        self.rng = np.random.default_rng(_stable_seed(seed, scenario_key, business_name))
        self.start = today - timedelta(days=HISTORY_DAYS)

        self._txns: list[Transaction] = []
        self._allocs: list[Allocation] = []
        self._invoices: list[Invoice] = []
        self._obligations: list[Obligation] = []
        self._inv_counter = {"sales": 1000, "purchase": 5000}

    # ───────────────────────── helpers ──────────────────────────

    def _season(self, d: date) -> float:
        return self.profile.seasonality[d.month - 1]

    def _recent(self, d: date) -> bool:
        return (self.today - d).days <= self.scenario.recent_window_days

    def _next_no(self, kind: str) -> str:
        self._inv_counter[kind] += 1
        prefix = "INV" if kind == "sales" else "PUR"
        return f"{prefix}-{self._inv_counter[kind]}"

    def _txn(self, *, account: Account, d: date, paise: int, direction: str,
             narration: str, category: str, counterparty_id: str | None = None,
             reference_no: str | None = None, source: str = "bank_csv",
             gross: int | None = None, fee: int = 0, evidence: str = Evidence.VERIFIED_ACTUAL,
             confidence: float = 0.95) -> Transaction:
        t = Transaction(
            id=_uid(), business_id=self.biz.id, account_id=account.id, counterparty_id=counterparty_id,
            source_system=source, source_ref=reference_no,
            value_date=d, posting_date=d, amount_paise=paise, direction=direction,
            narration=narration, reference_no=reference_no, category=category,
            category_confidence=confidence, category_source="synthetic",
            evidence=evidence, recon_status=ReconStatus.UNRECONCILED,
            gross_paise=gross, fee_paise=fee, allocated_paise=0,
            raw_json={"generated": True, "scenario": self.scenario.key},
            transform_log_json=[{"step": "generate", "source": "synthetic"}],
        )
        t.fingerprint = fingerprint(
            business_id=self.biz.id, account_id=account.id, value_date=d,
            amount_paise=paise, direction=direction, reference_no=reference_no,
            narration=narration,
        )
        self._txns.append(t)
        return t

    def _allocate(self, txn: Transaction, inv: Invoice, paise: int, why: str) -> None:
        paise = min(paise, inv.total_paise - inv.settled_paise)
        if paise <= 0:
            return
        self._allocs.append(Allocation(
            id=_uid(), business_id=self.biz.id, transaction_id=txn.id, invoice_id=inv.id,
            amount_paise=paise, method="exact_ref", confidence=0.99, rationale=why,
        ))
        inv.settled_paise += paise
        txn.allocated_paise = min(txn.gross_paise or txn.amount_paise,
                                  txn.allocated_paise + paise)
        if inv.first_payment_date is None or txn.value_date < inv.first_payment_date:
            inv.first_payment_date = txn.value_date
        if inv.outstanding_paise <= 0:
            inv.status = InvoiceStatus.PAID
            inv.settled_date = txn.value_date
            txn.recon_status = ReconStatus.MATCHED
        else:
            inv.status = InvoiceStatus.PART_PAID
            txn.recon_status = ReconStatus.PARTIALLY_MATCHED

    # ───────────────────────── build steps ──────────────────────────

    def build(self) -> GeneratedLedger:
        self._make_business()
        self._make_accounts()
        self._make_counterparties()
        self._make_loan()
        self._make_sales_cycle()
        self._make_purchase_cycle()
        self._make_operating_costs()
        self._make_statutory()
        self._make_noise()
        self._settle_opening_balance()
        self._future_obligations()
        self._prune_future_documents()
        self._finalise_invoice_status()
        return GeneratedLedger(
            business=self.biz, accounts=self.accounts, counterparties=self.parties,
            invoices=self._invoices, transactions=self._txns, allocations=self._allocs,
            obligations=self._obligations, loans=self.loans, report=self._report(),
        )

    def _make_business(self) -> None:
        self.biz = Business(
            id=_uid(), name=self.business_name,
            legal_name=f"{self.business_name} (Proprietorship)",
            industry=self.industry, gstin="36ABCDE1234F1Z5",
            city="Hyderabad", state_code="36", msme_class="small",
            udyam_number="UDYAM-TS-20-0001234",
            is_demo=True, demo_scenario=self.scenario.key,
            safety_buffer_paise=3_00_000_00, target_runway_weeks=8.0,
            max_customer_concentration=0.35, max_borrowing_apr=0.24,
            min_order_margin=0.10, risk_appetite="balanced",
            settings_json={
                "generated_at": self.today.isoformat(), "seed": self.seed,
                "scenario": self.scenario.key, "scenario_label": self.scenario.label,
                "data_provenance": "SYNTHETIC - generated by app.seed.generator",
            },
        )

    def _make_accounts(self) -> None:
        self.current = Account(
            id=_uid(), business_id=self.biz.id, name="Current A/c - HDFC Bank", kind=AccountKind.CURRENT,
            bank_name="HDFC Bank", masked_number="XXXX4417", opening_balance_paise=0,
            opening_date=self.start, overdraft_limit_paise=15_00_000_00,
            restricted_paise=0, source_system="bank_csv",
        )
        self.cash = Account(
            id=_uid(), business_id=self.biz.id, name="Cash in hand", kind=AccountKind.CASH,
            masked_number=None, opening_balance_paise=45_000_00, opening_date=self.start,
            source_system="manual",
        )
        self.fd = Account(
            id=_uid(), business_id=self.biz.id, name="Fixed Deposit (lien-marked for OD)", kind=AccountKind.SAVINGS,
            bank_name="HDFC Bank", masked_number="XXXX9902",
            opening_balance_paise=5_00_000_00, opening_date=self.start,
            restricted_paise=5_00_000_00, source_system="manual",
        )
        self.accounts = [self.current, self.cash, self.fd]

    def _make_counterparties(self) -> None:
        self.parties: list[Counterparty] = []
        self.customers: list[tuple[Counterparty, CustomerSpec]] = []
        for spec in WHOLESALE_CUSTOMERS:
            cp = Counterparty(
                id=_uid(), business_id=self.biz.id, name=spec.name, normalised_name=party_key(spec.name),
                party_type=PartyType.CUSTOMER, sector=spec.sector, region=spec.region,
                credit_days=spec.credit_days,
                credit_limit_paise=rupees_to_paise(self.annual_revenue * spec.share * 0.25),
                contact_name=f"Accounts - {spec.name.split()[0]}",
                contact_phone=f"+91 9{self.rng.integers(100000000, 999999999)}",
                aliases_json=[spec.name.upper(), spec.name.split()[0].upper()],
            )
            self.parties.append(cp)
            self.customers.append((cp, spec))

        self.suppliers: list[tuple[Counterparty, float, int]] = []
        for name, sector, share, cd, msme, disc, disc_days in WHOLESALE_SUPPLIERS:
            cp = Counterparty(
                id=_uid(), business_id=self.biz.id, name=name, normalised_name=party_key(name),
                party_type=PartyType.SUPPLIER, sector=sector, region="Telangana",
                msme_class=msme, credit_days=cd,
                early_payment_discount_pct=disc, early_payment_days=disc_days,
                aliases_json=[name.upper().split()[0]],
            )
            self.parties.append(cp)
            self.suppliers.append((cp, share, cd))

        for nm, pt in [("Staff Payroll", PartyType.EMPLOYEE),
                       ("GST Department", PartyType.STATUTORY),
                       ("Telangana Electricity", PartyType.SUPPLIER),
                       ("Godown Landlord", PartyType.SUPPLIER),
                       ("HDFC Bank (Term Loan)", PartyType.LENDER)]:
            self.parties.append(Counterparty(
                id=_uid(), business_id=self.biz.id, name=nm, normalised_name=party_key(nm),
                party_type=pt, credit_days=0,
            ))

    def _make_loan(self) -> None:
        emi = rupees_to_paise(62_500)
        self.loans = [Loan(
            id=_uid(), business_id=self.biz.id, lender="HDFC Bank", kind="term",
            principal_paise=rupees_to_paise(30_00_000),
            outstanding_paise=rupees_to_paise(16_80_000),
            annual_rate=0.135, emi_paise=emi, emi_day=7,
            start_date=self.start - timedelta(days=400),
            end_date=self.today + timedelta(days=810), is_active=True,
        )]
        self.emi_paise = emi

    # ---- sales ------------------------------------------------------

    def _daily_revenue(self, d: date) -> float:
        """Rupees of sales invoiced on a given day."""
        if d.weekday() == 6:                     # Sunday: trade is closed
            return 0.0
        base = self.annual_revenue / 310.0       # ~310 trading days
        mult = self._season(d)
        if self._recent(d):
            mult *= self.scenario.revenue_multiplier
        noise = float(self.rng.lognormal(mean=0.0, sigma=self.profile.revenue_cv))
        return base * mult * noise

    def _make_sales_cycle(self) -> None:
        shares = np.array([s.share for _, s in self.customers], dtype=float)
        shares = shares / shares.sum()
        end = self.today + timedelta(days=FORWARD_INVOICE_DAYS)
        d = self.start
        while d <= end:
            rev = self._daily_revenue(d)
            if rev > 1000:
                n_inv = int(self.rng.integers(1, 4))
                picks = self.rng.choice(len(self.customers), size=n_inv, replace=False, p=shares)
                parts = split_proportionally(rupees_to_paise(rev),
                                             [float(self.rng.uniform(0.6, 1.4)) for _ in range(n_inv)])
                for idx, amount in zip(picks, parts):
                    if amount < 100_00:
                        continue
                    cp, spec = self.customers[int(idx)]
                    self._emit_sales_invoice(cp, spec, d, amount)
            d += timedelta(days=1)

    def _emit_sales_invoice(self, cp: Counterparty, spec: CustomerSpec, d: date, total_paise: int) -> None:
        gst_rate = 0.18
        taxable = int(round(total_paise / (1 + gst_rate)))
        inv = Invoice(
            id=_uid(), business_id=self.biz.id, counterparty_id=cp.id, kind=InvoiceKind.SALES,
            invoice_no=self._next_no("sales"), issue_date=d,
            due_date=d + timedelta(days=spec.credit_days), credit_days=spec.credit_days,
            taxable_paise=taxable, tax_paise=total_paise - taxable, total_paise=total_paise,
            settled_paise=0, written_off_paise=0,
            gst_rate=gst_rate, place_of_supply="36", has_written_agreement=True,
            source_system="synthetic", evidence=Evidence.VERIFIED_ACTUAL,
        )
        self._invoices.append(inv)

        # Payment behaviour: a per-customer lognormal-ish delay around the due
        # date, widened by the scenario, plus an extra slip for the largest
        # customer in the delay scenarios.
        delay_mean = spec.delay_mean * self.scenario.delay_multiplier
        if spec is self.customers[0][1] and self.scenario.extra_delay_on_top_customer:
            # only for invoices issued inside the recent window
            if (self.today - d).days <= 150:
                delay_mean += self.scenario.extra_delay_on_top_customer
        # Structure that genuinely exists in Indian trade credit and that a
        # per-customer average cannot capture:
        #   * large invoices clear slower than small ones (approval chains),
        #   * delays stretch through the post-festive quarter,
        #   * a deteriorating buyer drifts later month on month.
        typical = max(1.0, self.annual_revenue * spec.share / 200.0 * 100.0)
        size_effect = 4.2 * float(np.log(max(0.15, total_paise / typical)))
        due_m = (d + timedelta(days=spec.credit_days)).month
        season_effect = {11: 5.0, 12: 4.0, 1: 2.5, 6: -2.0, 7: -2.0}.get(due_m, 0.0)
        months_elapsed = (d.year - self.start.year) * 12 + (d.month - self.start.month)
        drift = spec.drift_per_month * months_elapsed
        delay_mean = delay_mean + size_effect + season_effect + drift
        delay = float(self.rng.normal(delay_mean, spec.delay_sd * self.scenario.delay_multiplier))
        # Month-end push: Indian buyers cluster payments at month end.
        pay_date = inv.due_date + timedelta(days=int(round(max(-5.0, delay))))
        if self.rng.random() < 0.35:
            nxt_month = (pay_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            month_end = nxt_month - timedelta(days=1)
            if 0 < (month_end - pay_date).days <= 6:
                pay_date = month_end

        if self.rng.random() < spec.default_rate:
            return  # never paid - stays outstanding

        if pay_date > self.today:
            return  # legitimately still open

        if self.rng.random() < spec.partial_rate:
            first = int(total_paise * float(self.rng.uniform(0.35, 0.65)))
            self._receive(cp, inv, pay_date, first, part=1)
            second_date = pay_date + timedelta(days=int(self.rng.integers(6, 26)))
            if second_date <= self.today:
                self._receive(cp, inv, second_date, total_paise - first, part=2)
        else:
            self._receive(cp, inv, pay_date, total_paise, part=0)

    def _receive(self, cp: Counterparty, inv: Invoice, d: date, paise: int, *, part: int) -> None:
        if paise <= 0:
            return
        # 22% of collections arrive through a payment gateway, net of MDR.
        via_gateway = self.rng.random() < 0.22
        if via_gateway:
            fee = max(100, int(paise * 0.0085))
            net = paise - fee
            ref = f"RZP{self.rng.integers(10**9, 10**10)}"
            narration = (f"SETTLEMENT RAZORPAY {ref} {cp.name.upper()} "
                         f"{inv.invoice_no} GROSS {paise/100:.2f} FEE {fee/100:.2f}")
            txn = self._txn(account=self.current, d=d, paise=net, direction=Direction.CREDIT,
                            narration=narration, category=TxnCategory.CUSTOMER_RECEIPT,
                            counterparty_id=cp.id, reference_no=ref, source="payment_gateway",
                            gross=paise, fee=fee)
            self._allocate(txn, inv, paise,
                           f"gateway settlement {ref}: gross credited to {inv.invoice_no}, "
                           f"MDR of Rs {fee/100:.2f} booked separately")
            self._txn(account=self.current, d=d, paise=fee, direction=Direction.DEBIT,
                      narration=f"RAZORPAY FEE MDR {ref}", category=TxnCategory.GATEWAY_FEE,
                      reference_no=f"{ref}F", source="payment_gateway")
        else:
            mode = self.rng.choice(["NEFT", "RTGS", "IMPS", "UPI"], p=[0.45, 0.2, 0.15, 0.2])
            ref = f"{mode}{self.rng.integers(10**9, 10**10)}"
            suffix = {0: "", 1: " PART-1", 2: " PART-2"}[part]
            narration = f"{mode} CR-{cp.name.upper()}-{inv.invoice_no}{suffix}"
            txn = self._txn(account=self.current, d=d, paise=paise, direction=Direction.CREDIT,
                            narration=narration, category=TxnCategory.CUSTOMER_RECEIPT,
                            counterparty_id=cp.id, reference_no=ref)
            self._allocate(txn, inv, paise, f"{mode} reference {ref} quotes {inv.invoice_no}")

    # ---- purchases ---------------------------------------------------

    def _make_purchase_cycle(self) -> None:
        """Purchases track sales at (1 - gross_margin), raised ahead of the sale."""
        monthly: dict[tuple[int, int], int] = {}
        for inv in self._invoices:
            if inv.kind != InvoiceKind.SALES:
                continue
            key = (inv.issue_date.year, inv.issue_date.month)
            monthly[key] = monthly.get(key, 0) + inv.taxable_paise

        shares = [s for _, s, _ in self.suppliers]
        for (yr, mo), taxable in sorted(monthly.items()):
            cogs = int(taxable * (1 - self.profile.gross_margin))
            month_start = date(yr, mo, 1)
            buy_month = month_start - timedelta(days=self.profile.cogs_lead_days)
            if buy_month < self.start or buy_month > self.today + timedelta(days=30):
                continue
            if self._recent(buy_month):
                cogs = int(cogs * self.scenario.cost_multiplier)
            parts = split_proportionally(cogs, shares)
            for (cp, _share, cd), amount in zip(self.suppliers, parts):
                if amount < 5000_00:
                    continue
                n = int(self.rng.integers(1, 4))
                for sub in split_proportionally(amount, [float(self.rng.uniform(0.7, 1.3)) for _ in range(n)]):
                    if sub < 2000_00:
                        continue
                    day = int(self.rng.integers(1, 29))
                    issue = buy_month.replace(day=min(day, 28))
                    self._emit_purchase_invoice(cp, cd, issue, sub)

    def _emit_purchase_invoice(self, cp: Counterparty, credit_days: int, d: date, taxable: int) -> None:
        gst_rate = 0.18
        tax = int(round(taxable * gst_rate))
        total = taxable + tax
        inv = Invoice(
            id=_uid(), business_id=self.biz.id, counterparty_id=cp.id, kind=InvoiceKind.PURCHASE,
            invoice_no=self._next_no("purchase"), issue_date=d,
            due_date=d + timedelta(days=credit_days), credit_days=credit_days,
            taxable_paise=taxable, tax_paise=tax, total_paise=total, gst_rate=gst_rate,
            settled_paise=0, written_off_paise=0,
            has_written_agreement=cp.msme_class in (None, "medium") or True,
            source_system="synthetic", evidence=Evidence.VERIFIED_ACTUAL,
        )
        self._invoices.append(inv)

        # We pay close to terms, a little late when cash is tight (scenario C/E).
        stress = 1.0
        if self.scenario.key in ("C", "E") and self._recent(d):
            stress = 2.4
        slip = float(self.rng.normal(1.5 * stress, 3.0))
        pay_date = inv.due_date + timedelta(days=int(round(max(-8.0, slip))))
        if pay_date > self.today:
            return
        ref = f"NEFT{self.rng.integers(10**9, 10**10)}"
        txn = self._txn(account=self.current, d=pay_date, paise=total, direction=Direction.DEBIT,
                        narration=f"NEFT DR-{cp.name.upper()}-{inv.invoice_no} SUPPLIER PAYMENT",
                        category=TxnCategory.SUPPLIER_PAYMENT, counterparty_id=cp.id, reference_no=ref)
        self._allocate(txn, inv, total, f"NEFT reference {ref} quotes {inv.invoice_no}")

    # ---- operating costs ---------------------------------------------

    def _month_iter(self):
        d = self.start.replace(day=1)
        while d <= self.today + timedelta(days=40):
            yield d
            d = (d + timedelta(days=32)).replace(day=1)

    def _make_operating_costs(self) -> None:
        revenue_by_month: dict[tuple[int, int], int] = {}
        for inv in self._invoices:
            if inv.kind == InvoiceKind.SALES:
                k = (inv.issue_date.year, inv.issue_date.month)
                revenue_by_month[k] = revenue_by_month.get(k, 0) + inv.taxable_paise

        payroll_base = None
        for m in self._month_iter():
            rev = revenue_by_month.get((m.year, m.month), 0)
            opex = int(rev * self.profile.opex_ratio_of_revenue)
            payroll = int(opex * self.profile.payroll_share_of_opex)
            # Payroll is sticky: it does not track a bad month down.
            payroll_base = payroll if payroll_base is None else int(0.82 * payroll_base + 0.18 * payroll)
            payroll = max(payroll_base, 1_60_000_00)

            pay_day = self._business_day(m.replace(day=1) + timedelta(days=1))
            if pay_day <= self.today:
                self._txn(account=self.current, d=pay_day, paise=payroll, direction=Direction.DEBIT,
                          narration=f"SALARY PAYOUT {m.strftime('%b %Y').upper()} STAFF 14 NOS",
                          category=TxnCategory.PAYROLL, reference_no=f"SAL{m:%Y%m}")
            else:
                self._obligations.append(Obligation(
                    id=_uid(), business_id=self.biz.id, kind=ObligationKind.PAYROLL,
                    label=f"Payroll - {m.strftime('%B %Y')}", due_date=pay_day,
                    amount_paise=payroll, evidence=Evidence.OWNER_ESTIMATE,
                    is_recurring=True, recurrence="monthly", reserve_cash=True,
                    source_system="derived",
                    detail_json={"basis": "trailing payroll with 0.82 smoothing", "headcount": 14},
                ))

            rent = 1_10_000_00
            rent_day = self._business_day(m.replace(day=5))
            if rent_day <= self.today:
                self._txn(account=self.current, d=rent_day, paise=rent, direction=Direction.DEBIT,
                          narration=f"RENT GODOWN+OFFICE {m.strftime('%b %Y').upper()}",
                          category=TxnCategory.RENT, reference_no=f"RENT{m:%Y%m}")
            else:
                self._obligations.append(Obligation(
                    id=_uid(), business_id=self.biz.id, kind=ObligationKind.RENT,
                    label=f"Godown & office rent - {m.strftime('%B %Y')}", due_date=rent_day,
                    amount_paise=rent, evidence=Evidence.VERIFIED_ACTUAL,
                    is_recurring=True, recurrence="monthly", source_system="contract"))

            util = int(opex * 0.11) + int(self.rng.integers(8_000_00, 22_000_00))
            u_day = self._business_day(m.replace(day=12))
            if u_day <= self.today:
                self._txn(account=self.current, d=u_day, paise=util, direction=Direction.DEBIT,
                          narration=f"ELECTRICITY TGSPDCL BILL {m.strftime('%b %Y').upper()}",
                          category=TxnCategory.UTILITIES, reference_no=f"UTL{m:%Y%m}")

            freight = int(opex * 0.17)
            if freight > 5000_00:
                f_day = self._business_day(m.replace(day=min(18, 28)))
                if f_day <= self.today:
                    self._txn(account=self.current, d=f_day, paise=freight, direction=Direction.DEBIT,
                              narration=f"FREIGHT CHARMINAR LOGISTICS {m.strftime('%b').upper()}",
                              category=TxnCategory.FREIGHT, reference_no=f"FRT{m:%Y%m}")

            emi_day = self._business_day(m.replace(day=7))
            if emi_day <= self.today:
                self._txn(account=self.current, d=emi_day, paise=self.emi_paise, direction=Direction.DEBIT,
                          narration="EMI TERM LOAN HDFC AC 4417 PRINCIPAL+INT",
                          category=TxnCategory.LOAN_REPAYMENT, reference_no=f"EMI{m:%Y%m}")
            else:
                self._obligations.append(Obligation(
                    id=_uid(), business_id=self.biz.id, kind=ObligationKind.LOAN_EMI,
                    label=f"Term loan EMI - {m.strftime('%B %Y')}", due_date=emi_day,
                    amount_paise=self.emi_paise, evidence=Evidence.VERIFIED_ACTUAL,
                    is_recurring=True, recurrence="monthly", source_system="loan_schedule"))

    def _business_day(self, d: date) -> date:
        while d.weekday() == 6:
            d += timedelta(days=1)
        return d

    # ---- statutory ----------------------------------------------------

    def _make_statutory(self) -> None:
        """GSTR-3B liability = output GST on sales - input GST on purchases,
        paid by the 20th of the following month."""
        out_tax: dict[tuple[int, int], int] = {}
        in_tax: dict[tuple[int, int], int] = {}
        for inv in self._invoices:
            k = (inv.issue_date.year, inv.issue_date.month)
            if inv.kind == InvoiceKind.SALES:
                out_tax[k] = out_tax.get(k, 0) + inv.tax_paise
            else:
                in_tax[k] = in_tax.get(k, 0) + inv.tax_paise

        for k in sorted(set(out_tax) | set(in_tax)):
            liab = max(0, out_tax.get(k, 0) - in_tax.get(k, 0))
            if liab <= 0:
                continue
            yr, mo = k
            nxt = (date(yr, mo, 1) + timedelta(days=32)).replace(day=20)
            if nxt <= self.today:
                self._txn(account=self.current, d=self._business_day(nxt), paise=liab,
                          direction=Direction.DEBIT,
                          narration=f"GST CHALLAN PMT-06 GSTR-3B {date(yr,mo,1).strftime('%b %Y').upper()}",
                          category=TxnCategory.GST_PAYMENT, reference_no=f"GST{yr}{mo:02d}")
            else:
                self._obligations.append(Obligation(
                    id=_uid(), business_id=self.biz.id, kind=ObligationKind.GST,
                    label=f"GSTR-3B liability for {date(yr,mo,1).strftime('%B %Y')}",
                    due_date=nxt, amount_paise=liab, evidence=Evidence.OWNER_ESTIMATE,
                    reserve_cash=True, source_system="derived",
                    detail_json={"output_tax_paise": out_tax.get(k, 0),
                                 "input_tax_credit_paise": in_tax.get(k, 0),
                                 "basis": "output GST on recorded sales minus ITC on recorded purchases",
                                 "verified": False}))

        # TDS on freight/rent (194C/194I), deposited by the 7th.
        for m in self._month_iter():
            tds = int(self.rng.integers(6_000_00, 14_000_00))
            d = self._business_day((m + timedelta(days=32)).replace(day=7))
            if d <= self.today:
                self._txn(account=self.current, d=d, paise=tds, direction=Direction.DEBIT,
                          narration=f"TDS CHALLAN ITNS-281 {m.strftime('%b %Y').upper()} 194C/194I",
                          category=TxnCategory.TAX_OTHER, reference_no=f"TDS{m:%Y%m}")

    # ---- realistic mess -------------------------------------------------

    def _make_noise(self) -> None:
        """Bank charges, interest, refunds, an ambiguous pair and a few
        genuinely unidentifiable credits - the ledger must cope with these."""
        d = self.start
        while d <= self.today:
            if d.day == 28:
                self._txn(account=self.current, d=d, paise=int(self.rng.integers(400_00, 1800_00)),
                          direction=Direction.DEBIT,
                          narration="BANK CHARGES NEFT/RTGS + SMS ALERT + GST ON CHARGES",
                          category=TxnCategory.BANK_CHARGES, reference_no=f"BC{d:%Y%m}")
            if d.day == 30 and d.month % 3 == 0:
                self._txn(account=self.fd, d=d, paise=int(self.rng.integers(12_000_00, 18_000_00)),
                          direction=Direction.CREDIT, narration="FD INTEREST CREDIT QUARTERLY",
                          category=TxnCategory.INTEREST_INCOME, reference_no=f"INT{d:%Y%m}")
            d += timedelta(days=1)

        # Refunds to customers for short supply
        for _ in range(7):
            off = int(self.rng.integers(30, HISTORY_DAYS))
            dd = self.today - timedelta(days=off)
            cp, _ = self.customers[int(self.rng.integers(0, len(self.customers)))]
            self._txn(account=self.current, d=dd, paise=int(self.rng.integers(8_000_00, 60_000_00)),
                      direction=Direction.DEBIT,
                      narration=f"REFUND CREDIT NOTE SHORT SUPPLY {cp.name.upper()}",
                      category=TxnCategory.REFUND_OUT, counterparty_id=cp.id,
                      reference_no=f"CN{self.rng.integers(10000,99999)}")

        # Unidentifiable credits - these must stay visible as unreconciled.
        for _ in range(5):
            off = int(self.rng.integers(5, 200))
            dd = self.today - timedelta(days=off)
            self._txn(account=self.current, d=dd, paise=int(self.rng.integers(15_000_00, 90_000_00)),
                      direction=Direction.CREDIT,
                      narration=f"UPI/P2A/{self.rng.integers(10**11, 10**12)}/PAYMENT",
                      category=TxnCategory.UNCATEGORISED, reference_no=None,
                      evidence=Evidence.IMPORTED_ACTUAL, confidence=0.2)

        # One double-paid supplier bill: identical amount, one day apart, no
        # shared reference. The duplicate detector must flag, not delete.
        dd = self.today - timedelta(days=41)
        cp = self.suppliers[0][0]
        amt = 1_84_500_00
        for i in range(2):
            self._txn(account=self.current, d=dd + timedelta(days=i), paise=amt,
                      direction=Direction.DEBIT,
                      narration=f"NEFT DR-{cp.name.upper()}-BILL SETTLEMENT NOV",
                      category=TxnCategory.SUPPLIER_PAYMENT, counterparty_id=cp.id,
                      reference_no=None, evidence=Evidence.IMPORTED_ACTUAL)

        # Counter cash sales, petty cash, and a weekly sweep of surplus cash
        # into the bank. The sweep is a *paired* internal transfer, so total
        # credits and debits still net to zero across the two accounts.
        running = self.cash.opening_balance_paise
        d = self.start
        while d <= self.today:
            if d.weekday() != 6 and self.rng.random() < 0.3:
                amt = int(self.rng.integers(3_000_00, 25_000_00))
                self._txn(account=self.cash, d=d, paise=amt, direction=Direction.CREDIT,
                          narration="COUNTER CASH SALES", category=TxnCategory.OTHER_INCOME,
                          reference_no=None, source="manual")
                running += amt
            if d.day == 15:
                amt = min(running, int(self.rng.integers(20_000_00, 60_000_00)))
                if amt > 0:
                    self._txn(account=self.cash, d=d, paise=amt, direction=Direction.DEBIT,
                              narration="PETTY CASH EXPENSES CONSOLIDATED",
                              category=TxnCategory.OTHER_EXPENSE, reference_no=None, source="manual")
                    running -= amt
            if d.weekday() == 5 and running > 1_50_000_00:
                sweep = running - 50_000_00
                ref = f"CSHDEP{d:%Y%m%d}"
                self._txn(account=self.cash, d=d, paise=sweep, direction=Direction.DEBIT,
                          narration=f"CASH DEPOSITED TO BANK SELF TRANSFER {ref}",
                          category=TxnCategory.TRANSFER, reference_no=ref, source="manual")
                self._txn(account=self.current, d=d, paise=sweep, direction=Direction.CREDIT,
                          narration=f"CASH DEPOSIT BY SELF {ref} OWN ACCOUNT",
                          category=TxnCategory.TRANSFER, reference_no=f"{ref}B", source="bank_csv")
                running -= sweep
            d += timedelta(days=1)

    # ---- close the books -------------------------------------------------

    def _settle_opening_balance(self) -> None:
        """Choose each opening balance so the generated closing balance is the
        scenario's target. This is what makes
        ``opening + credits - debits == closing`` hold by construction."""
        for acct in self.accounts:
            net = sum(t.signed_paise for t in self._txns
                      if t.account_id == acct.id and t.value_date <= self.today)
            if acct is self.current:
                target = self.scenario.target_closing_cash - self.cash.opening_balance_paise - \
                    sum(t.signed_paise for t in self._txns
                        if t.account_id == self.cash.id and t.value_date <= self.today)
                acct.opening_balance_paise = target - net
            elif acct is self.fd:
                acct.opening_balance_paise = 5_00_000_00
        self._opening_net = {a.id: a.opening_balance_paise for a in self.accounts}

    def _future_obligations(self) -> None:
        if self.scenario.add_expansion_opportunity:
            self._obligations.append(Obligation(
                id=_uid(), business_id=self.biz.id, kind=ObligationKind.OTHER,
                label="Shortlisted: automated carton sealer (quotation received)",
                due_date=self.today + timedelta(days=45), amount_paise=9_50_000_00,
                evidence=Evidence.OWNER_ESTIMATE, reserve_cash=False,
                source_system="manual",
                detail_json={"status": "under consideration, not committed",
                             "vendor": "Surya Packaging Machines",
                             "expected_annual_saving_paise": 2_40_000_00}))
        self._obligations.append(Obligation(
            id=_uid(), business_id=self.biz.id, kind=ObligationKind.INSURANCE,
            label="Godown fire & burglary policy renewal",
            due_date=self.today + timedelta(days=38), amount_paise=74_000_00,
            evidence=Evidence.VERIFIED_ACTUAL, is_recurring=True, recurrence="yearly",
            source_system="contract"))

    def _prune_future_documents(self) -> None:
        """Drop documents dated after 'today'.

        The sales cycle is generated 75 days forward so that the purchase
        cycle, which is lead-shifted, has demand to work from. Those forward
        invoices must never reach the ledger: a business does not hold
        invoices it has not issued yet, and counting them as receivables
        would overstate the forecast by roughly two months of sales.
        """
        keep, dropped = [], set()
        for inv in self._invoices:
            if inv.issue_date <= self.today:
                keep.append(inv)
            else:
                dropped.add(inv.id)
        self._invoices = keep
        if dropped:
            self._allocs = [a for a in self._allocs if a.invoice_id not in dropped]
        self._txns = [t for t in self._txns if t.value_date <= self.today]

    def _finalise_invoice_status(self) -> None:
        for inv in self._invoices:
            if inv.outstanding_paise <= 0:
                inv.status = InvoiceStatus.PAID
            elif inv.settled_paise > 0:
                inv.status = InvoiceStatus.PART_PAID
            else:
                inv.status = InvoiceStatus.OPEN
            if inv.status in (InvoiceStatus.OPEN, InvoiceStatus.PART_PAID) and inv.due_date < self.today:
                inv.status = InvoiceStatus.OVERDUE

    def _report(self) -> dict:
        hist = [t for t in self._txns if t.value_date <= self.today]
        credits = sum(t.amount_paise for t in hist if t.direction == Direction.CREDIT)
        debits = sum(t.amount_paise for t in hist if t.direction == Direction.DEBIT)
        opening = sum(a.opening_balance_paise for a in self.accounts)
        ar = sum(i.outstanding_paise for i in self._invoices
                 if i.kind == InvoiceKind.SALES and i.issue_date <= self.today)
        ap = sum(i.outstanding_paise for i in self._invoices
                 if i.kind == InvoiceKind.PURCHASE and i.issue_date <= self.today)
        return {
            "scenario": self.scenario.key, "scenario_label": self.scenario.label,
            "seed": self.seed, "today": self.today.isoformat(),
            "history_days": HISTORY_DAYS,
            "accounts": len(self.accounts), "counterparties": len(self.parties),
            "invoices": len(self._invoices), "transactions": len(hist),
            "future_dated_invoices": len(self._invoices) - sum(
                1 for i in self._invoices if i.issue_date <= self.today),
            "allocations": len(self._allocs),
            "opening_balance_paise": opening, "credits_paise": credits, "debits_paise": debits,
            "closing_balance_paise": opening + credits - debits,
            "target_closing_paise": self.scenario.target_closing_cash,
            "receivables_paise": ar, "payables_paise": ap,
            "obligations": len(self._obligations),
        }
