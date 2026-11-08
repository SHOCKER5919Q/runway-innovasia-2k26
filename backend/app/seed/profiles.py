"""Industry and demo-scenario profiles for the synthetic MSME generator."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.core.enums import Industry


@dataclass(frozen=True)
class IndustryProfile:
    """Financial physics of an industry.

    These drive both the data generator *and* the forecaster's priors, which
    is why they live outside the generator: a real business uploading its own
    data gets the same industry prior without any synthetic data involved.
    """
    key: str
    label: str
    gross_margin: float            # (sales - COGS) / sales
    cogs_lead_days: int            # purchase raised this many days before sale
    default_customer_credit_days: int
    default_supplier_credit_days: int
    opex_ratio_of_revenue: float   # payroll+rent+utilities+freight as share of revenue
    payroll_share_of_opex: float
    revenue_cv: float              # coefficient of variation of weekly revenue
    seasonality: tuple[float, ...] = field(default=(1.0,) * 12)  # monthly multipliers, Jan..Dec
    inventory_days: int = 0
    notes: str = ""


# Indian festive demand peaks Sep-Nov (Dussehra/Diwali) for trade-facing
# businesses and dips in Feb-Mar; services are flatter but dip in April
# (fiscal-year transition).
_TRADE_SEASON = (0.92, 0.88, 0.95, 0.97, 1.00, 0.98, 1.00, 1.05, 1.18, 1.22, 1.10, 0.95)
_MFG_SEASON = (0.95, 0.93, 1.05, 0.90, 0.98, 1.00, 1.02, 1.06, 1.14, 1.16, 1.05, 0.96)
_RETAIL_SEASON = (0.90, 0.86, 0.94, 0.96, 1.02, 0.95, 0.98, 1.04, 1.20, 1.30, 1.12, 1.03)
_SERVICES_SEASON = (1.0, 1.0, 1.08, 0.88, 0.98, 1.0, 1.02, 1.0, 1.02, 1.04, 1.0, 0.98)

PROFILES: dict[str, IndustryProfile] = {
    Industry.WHOLESALE: IndustryProfile(
        key=Industry.WHOLESALE, label="Wholesale / Distribution",
        gross_margin=0.185, cogs_lead_days=12,
        default_customer_credit_days=45, default_supplier_credit_days=30,
        opex_ratio_of_revenue=0.075, payroll_share_of_opex=0.52,
        revenue_cv=0.22, seasonality=_TRADE_SEASON, inventory_days=28,
        notes="High volume, thin margin. Cash risk comes from customer credit "
              "periods exceeding supplier credit periods.",
    ),
    Industry.MANUFACTURING: IndustryProfile(
        key=Industry.MANUFACTURING, label="Manufacturing",
        gross_margin=0.28, cogs_lead_days=30,
        default_customer_credit_days=60, default_supplier_credit_days=30,
        opex_ratio_of_revenue=0.14, payroll_share_of_opex=0.60,
        revenue_cv=0.26, seasonality=_MFG_SEASON, inventory_days=45,
        notes="Raw material is bought and paid well before the sale is "
              "collected, so the working-capital cycle is the dominant risk.",
    ),
    Industry.RETAIL: IndustryProfile(
        key=Industry.RETAIL, label="Retail",
        gross_margin=0.24, cogs_lead_days=18,
        default_customer_credit_days=0, default_supplier_credit_days=21,
        opex_ratio_of_revenue=0.16, payroll_share_of_opex=0.45,
        revenue_cv=0.18, seasonality=_RETAIL_SEASON, inventory_days=35,
        notes="Collections are same-day, so receivables risk is low and the "
              "risk shifts to inventory and rent fixed costs.",
    ),
    Industry.SERVICES: IndustryProfile(
        key=Industry.SERVICES, label="Services",
        gross_margin=0.55, cogs_lead_days=0,
        default_customer_credit_days=30, default_supplier_credit_days=15,
        opex_ratio_of_revenue=0.38, payroll_share_of_opex=0.78,
        revenue_cv=0.30, seasonality=_SERVICES_SEASON, inventory_days=0,
        notes="Payroll dominates. Revenue is lumpy per project and customer "
              "concentration is usually the single biggest exposure.",
    ),
}


def get_profile(industry: str) -> IndustryProfile:
    return PROFILES.get(industry, PROFILES[Industry.WHOLESALE])


@dataclass(frozen=True)
class DemoScenario:
    key: str
    label: str
    summary: str
    delay_multiplier: float = 1.0           # scales every customer's payment delay
    revenue_multiplier: float = 1.0         # scales sales in the recent window
    cost_multiplier: float = 1.0            # scales purchase prices in the recent window
    target_closing_cash: int = 8_24_000_00  # paise, matches the reference UI board
    recent_window_days: int = 90
    extra_delay_on_top_customer: int = 0    # days, applied to the largest customer only
    add_expansion_opportunity: bool = False
    narrative: str = ""


SCENARIOS: dict[str, DemoScenario] = {
    "A": DemoScenario(
        key="A", label="Healthy business",
        summary="Stable collections, manageable obligations, comfortable buffer.",
        delay_multiplier=0.75, revenue_multiplier=1.05, target_closing_cash=14_60_000_00,
        narrative="Collections are arriving close to terms and the 13-week "
                  "projection stays above the safety buffer throughout.",
    ),
    "B": DemoScenario(
        key="B", label="Delayed payments",
        summary="The largest customer has slipped from 45-day to 70-day behaviour.",
        delay_multiplier=1.25, extra_delay_on_top_customer=22,
        target_closing_cash=8_24_000_00,
        narrative="Revenue is unchanged but cash conversion has stretched. The "
                  "problem shows up as a receivables-ageing shift before it "
                  "shows up in the bank balance.",
    ),
    "C": DemoScenario(
        key="C", label="Liquidity crisis",
        summary="Multiple receivables delayed while payroll and GST fall due.",
        delay_multiplier=1.75, extra_delay_on_top_customer=30,
        revenue_multiplier=0.88, target_closing_cash=3_10_000_00,
        narrative="Several large collections have slipped past the month-end "
                  "obligation cluster. The P10 path breaches the safety buffer "
                  "within the first few weeks.",
    ),
    "D": DemoScenario(
        key="D", label="Business expansion",
        summary="Healthy base with a large new order and an equipment decision on the table.",
        delay_multiplier=0.9, revenue_multiplier=1.12,
        target_closing_cash=11_40_000_00, add_expansion_opportunity=True,
        narrative="The business can fund growth, but the order's working-capital "
                  "peak lands before its collection does. This is the signature "
                  "'should I accept this order?' demonstration.",
    ),
    "E": DemoScenario(
        key="E", label="Adverse market conditions",
        summary="Revenue falling and input costs rising at the same time.",
        delay_multiplier=1.35, revenue_multiplier=0.78, cost_multiplier=1.14,
        target_closing_cash=5_80_000_00,
        narrative="A compound shock. Margin compresses while collections slow, "
                  "so the runway shortens from both ends at once.",
    ),
}

DEFAULT_SCENARIO = "B"
