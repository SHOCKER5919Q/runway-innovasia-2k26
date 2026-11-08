"""Create (or recreate) the demo workspace.

``python -m app.seed.seed --scenario B --reset`` wipes and rebuilds.
Every row written here is marked synthetic; see ``docs/DEMO_GUIDE.md``.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from sqlalchemy import delete, select

from app.core.db import Base, SessionLocal, create_all, engine
from app.core.enums import Role
from app.core.security import hash_password
from app.models import (
    Account, Alert, Allocation, AuditLog, ActualSnapshot, Business, BusinessState,
    Consent, CopilotMessage, Counterparty, ForecastPoint, ImportBatch, Invoice,
    Loan, Membership, ModelRun, Obligation, PaymentPrediction, PredictedSnapshot,
    Recommendation, Scenario, ScenarioDecision, SharedReport, SimulatedSnapshot,
    StateComparison, Transaction, TwinEvent, User, _uid,
)
from app.seed.generator import SyntheticBusinessGenerator
from app.seed.profiles import SCENARIOS

DEMO_USERS = [
    ("owner@runway.demo", "Amit Sharma", Role.OWNER, "demo1234", False),
    ("manager@runway.demo", "Priya Reddy", Role.MANAGER, "demo1234", False),
    ("ca@runway.demo", "S. Krishnan, FCA", Role.ACCOUNTANT, "demo1234", True),
]

# A second, smaller business so the accountant workspace and tenant-isolation
# tests have something real to work with.
SECOND_BUSINESS = dict(
    business_name="Deccan Precision Components",
    industry="manufacturing",
    annual_revenue_rupees=1_90_00_000,
    scenario_key="C",
    seed=77001,
)


def wipe_business(db, business_id: str) -> None:
    for model in (Allocation, Transaction, Invoice, Obligation, Loan, Counterparty,
                  Account, Alert, Recommendation, CopilotMessage, TwinEvent,
                  ForecastPoint, PaymentPrediction, ModelRun, ActualSnapshot,
                  PredictedSnapshot, SimulatedSnapshot, ScenarioDecision, Scenario,
                  StateComparison, BusinessState, ImportBatch, Consent, SharedReport,
                  AuditLog, Membership):
        db.execute(delete(model).where(model.business_id == business_id))
    db.execute(delete(Business).where(Business.id == business_id))
    db.commit()


def persist(db, led, *, users: list[User], roles: list[str]) -> Business:
    db.add(led.business)
    db.flush()
    for u, role in zip(users, roles):
        db.add(Membership(id=_uid(), user_id=u.id, business_id=led.business.id, role=role,
                          scopes_json=["read:*", "write:*"] if role != Role.VIEWER else ["read:*"]))
    for obj in (*led.accounts, *led.counterparties, *led.loans):
        db.add(obj)
    db.flush()
    db.add_all(led.invoices)
    db.flush()
    db.add_all(led.transactions)
    db.flush()
    db.add_all(led.allocations)
    db.add_all(led.obligations)
    db.commit()
    return led.business


def seed(scenario: str = "B", *, reset: bool = False, today: date | None = None,
         seed_value: int = 20260101, with_second: bool = True, verbose: bool = True) -> dict:
    today = today or date.today()
    if reset:
        Base.metadata.drop_all(bind=engine)
    create_all()
    db = SessionLocal()
    out: dict = {"scenario": scenario, "today": today.isoformat(), "businesses": []}
    try:
        users: list[User] = []
        for email, name, _role, pw, is_ca in DEMO_USERS:
            u = db.scalar(select(User).where(User.email == email))
            if not u:
                u = User(id=_uid(), email=email, full_name=name, password_hash=hash_password(pw),
                         is_accountant=is_ca, preferred_language="en")
                db.add(u)
            users.append(u)
        db.commit()

        for b in db.scalars(select(Business).where(Business.is_demo.is_(True))).all():
            wipe_business(db, b.id)

        gen = SyntheticBusinessGenerator(today=today, scenario_key=scenario, seed=seed_value)
        led = gen.build()
        biz = persist(db, led, users=users, roles=[Role.OWNER, Role.MANAGER, Role.ACCOUNTANT])
        out["businesses"].append({"id": biz.id, "name": biz.name, **led.report})

        if with_second:
            g2 = SyntheticBusinessGenerator(today=today, **SECOND_BUSINESS)
            led2 = g2.build()
            led2.business.name = SECOND_BUSINESS["business_name"]
            led2.business.city = "Medak"
            biz2 = persist(db, led2, users=[users[2]], roles=[Role.ACCOUNTANT])
            out["businesses"].append({"id": biz2.id, "name": biz2.name, **led2.report})

        # Run the real pipeline over the generated ledger so the demo exercises
        # the same code path an import does: duplicate detection, matching,
        # overdue refresh, then the three-state build.
        from app.ledger.normalise import detect_duplicate, mark_suspected_duplicate
        from app.ledger.reconciliation import reconcile_business, refresh_overdue
        from app.financial_states.state_manager import refresh as refresh_states

        for biz_row in db.scalars(select(Business).where(Business.is_demo.is_(True))).all():
            seen: dict[str, str] = {}
            for t in db.scalars(select(Transaction).where(
                    Transaction.business_id == biz_row.id).order_by(Transaction.value_date)).all():
                prior = seen.get(t.fingerprint)
                if prior:
                    mark_suspected_duplicate(
                        t, prior, "identical fingerprint with no distinguishing bank reference")
                else:
                    seen[t.fingerprint] = t.id
            stats = reconcile_business(db, biz_row.id)
            refresh_overdue(db, biz_row.id, today)
            db.commit()
            # Backfill forecast runs at past dates so the state-reconciliation
            # feature has real history to score instead of an empty table. Each
            # run is a genuine forecast made from the ledger as it stood on that
            # date, which is exactly what the accuracy report needs.
            from app.financial_states.state_manager import (
                build_actual, build_predicted, reconcile_forecasts)
            for back in (84, 63, 42, 21):
                past = today - timedelta(days=back)
                pa = build_actual(db, biz_row.id, past, trigger="backfill")
                build_predicted(db, biz_row.id, pa, trigger="backfill", paths=1500)
                db.commit()
            refresh_states(db, biz_row.id, today, trigger="seed")
            db.commit()
            acc = reconcile_forecasts(db, biz_row.id, today)
            db.commit()
            for entry in out["businesses"]:
                if entry["id"] == biz_row.id:
                    entry["forecast_accuracy"] = acc.get("cash_forecast_by_horizon", [])[:3]
            for entry in out["businesses"]:
                if entry["id"] == biz_row.id:
                    entry["reconciliation"] = stats

        db.add(Consent(
            id=_uid(), business_id=biz.id, purpose="accountant_access",
            scope_json=["read:ledger", "read:forecast", "read:reports"],
            granted_by_user_id=users[0].id, grantee="S. Krishnan, FCA",
            expires_at=None))
        db.commit()
    finally:
        db.close()
    if verbose:
        for b in out["businesses"]:
            print(f"  {b['name']:<34} txns={b['transactions']:<5} invoices={b['invoices']:<5} "
                  f"cash=Rs {b['target_closing_paise']/100:,.0f}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the RUNWAY demo workspace")
    ap.add_argument("--scenario", default="B", choices=sorted(SCENARIOS))
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables")
    ap.add_argument("--date", default=None, help="treat this ISO date as 'today'")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--no-second", action="store_true")
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    print(f"Seeding scenario {a.scenario} ({SCENARIOS[a.scenario].label}) as of {today} ...")
    seed(a.scenario, reset=a.reset, today=today, seed_value=a.seed, with_second=not a.no_second)
    print("Done. Sign in with owner@runway.demo / demo1234")


if __name__ == "__main__":
    main()
