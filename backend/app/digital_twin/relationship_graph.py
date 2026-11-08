"""The business financial relationship graph.

Nodes: the business, its accounts, customers, suppliers, open invoices,
obligations and loans. Edges carry the money relationship and its direction.

Built from relational PostgreSQL/SQLite tables rather than a graph database:
at MSME scale (hundreds of counterparties, thousands of invoices) the joins
are trivial, and adding a second datastore would buy nothing but operational
risk. ``docs/DIGITAL_TWIN_ARCHITECTURE.md`` records the threshold at which
that trade-off would flip.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.core.enums import InvoiceKind, InvoiceStatus, PartyType
from app.models import Account, Counterparty, Invoice, Loan, Obligation


def build(db, business_id: str, as_of: date, *, max_invoices_per_party: int = 4,
          min_amount_paise: int = 0) -> dict:
    from app.analytics.concentration import concentration
    from app.models import Business

    biz = db.get(Business, business_id)
    nodes: list[dict] = [{"id": f"biz:{business_id}", "type": "business", "label": biz.name,
                          "group": "core", "value": 100}]
    edges: list[dict] = []

    for a in db.scalars(select(Account).where(Account.business_id == business_id,
                                              Account.is_active.is_(True))).all():
        from app.analytics.cash import account_balance
        bal = account_balance(db, a, as_of)
        nodes.append({"id": f"acct:{a.id}", "type": "account", "label": a.name,
                      "group": "account", "value": bal.closing_paise,
                      "meta": {"kind": a.kind, "masked": a.masked_number,
                               "restricted_paise": a.restricted_paise,
                               "balance_paise": bal.closing_paise}})
        edges.append({"source": f"acct:{a.id}", "target": f"biz:{business_id}",
                      "type": "holds", "label": "balance", "value": bal.closing_paise})

    invs = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id, Invoice.issue_date <= as_of,
        Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED,
                               InvoiceStatus.WRITTEN_OFF]))).all()
    by_party: dict[str, list[Invoice]] = {}
    for i in invs:
        if i.outstanding_paise > min_amount_paise:
            by_party.setdefault(i.counterparty_id, []).append(i)

    conc = concentration(db, business_id, as_of)
    share_by_cp = {t["counterparty_id"]: t["share"] for t in conc["top_counterparties"]}

    parties = {c.id: c for c in db.scalars(select(Counterparty).where(
        Counterparty.business_id == business_id)).all()}
    for cp_id, rows in by_party.items():
        cp = parties.get(cp_id)
        if cp is None:
            continue
        total = sum(i.outstanding_paise for i in rows)
        overdue = sum(i.outstanding_paise for i in rows if i.due_date < as_of)
        is_customer = rows[0].kind == InvoiceKind.SALES
        nodes.append({
            "id": f"cp:{cp_id}", "type": "customer" if is_customer else "supplier",
            "label": cp.name, "group": "customer" if is_customer else "supplier",
            "value": total,
            "meta": {"sector": cp.sector, "region": cp.region,
                     "credit_days": cp.credit_days, "msme_class": cp.msme_class,
                     "outstanding_paise": total, "overdue_paise": overdue,
                     "open_invoices": len(rows),
                     "revenue_share": share_by_cp.get(cp_id, 0.0)}})
        edges.append({
            "source": f"cp:{cp_id}" if is_customer else f"biz:{business_id}",
            "target": f"biz:{business_id}" if is_customer else f"cp:{cp_id}",
            "type": "owes", "label": "receivable" if is_customer else "payable",
            "value": total,
            "meta": {"overdue_paise": overdue,
                     "overdue_share": round(overdue / total, 3) if total else 0}})
        for inv in sorted(rows, key=lambda i: -i.outstanding_paise)[:max_invoices_per_party]:
            nodes.append({
                "id": f"inv:{inv.id}", "type": "invoice", "label": inv.invoice_no,
                "group": "invoice", "value": inv.outstanding_paise,
                "meta": {"kind": inv.kind, "due_date": inv.due_date.isoformat(),
                         "days_past_due": (as_of - inv.due_date).days,
                         "outstanding_paise": inv.outstanding_paise,
                         "status": inv.status}})
            edges.append({"source": f"inv:{inv.id}", "target": f"cp:{cp_id}",
                          "type": "belongs_to", "label": "issued to" if is_customer else "received from",
                          "value": inv.outstanding_paise})

    for o in db.scalars(select(Obligation).where(
            Obligation.business_id == business_id, Obligation.is_paid.is_(False),
            Obligation.due_date >= as_of,
            Obligation.due_date <= as_of + timedelta(days=95))).all():
        nodes.append({"id": f"ob:{o.id}", "type": "obligation", "label": o.label,
                      "group": "obligation", "value": o.amount_paise,
                      "meta": {"kind": o.kind, "due_date": o.due_date.isoformat(),
                               "days_away": (o.due_date - as_of).days,
                               "evidence": o.evidence}})
        edges.append({"source": f"biz:{business_id}", "target": f"ob:{o.id}",
                      "type": "must_pay", "label": o.kind, "value": o.amount_paise})

    for ln in db.scalars(select(Loan).where(Loan.business_id == business_id,
                                            Loan.is_active.is_(True))).all():
        nodes.append({"id": f"loan:{ln.id}", "type": "loan", "label": f"{ln.lender} ({ln.kind})",
                      "group": "loan", "value": ln.outstanding_paise,
                      "meta": {"rate": ln.annual_rate, "emi_paise": ln.emi_paise,
                               "outstanding_paise": ln.outstanding_paise}})
        edges.append({"source": f"biz:{business_id}", "target": f"loan:{ln.id}",
                      "type": "owes", "label": "loan", "value": ln.outstanding_paise})

    return {
        "as_of": as_of.isoformat(), "nodes": nodes, "edges": edges,
        "stats": {
            "nodes": len(nodes), "edges": len(edges),
            "customers": sum(1 for n in nodes if n["type"] == "customer"),
            "suppliers": sum(1 for n in nodes if n["type"] == "supplier"),
            "open_invoices_shown": sum(1 for n in nodes if n["type"] == "invoice"),
            "receivable_total_paise": sum(e["value"] for e in edges
                                          if e["label"] == "receivable"),
            "payable_total_paise": sum(e["value"] for e in edges if e["label"] == "payable"),
        },
        "insights": _insights(nodes, edges, conc),
    }


def _insights(nodes, edges, conc) -> list[str]:
    out = []
    cust = [n for n in nodes if n["type"] == "customer"]
    if cust:
        top = max(cust, key=lambda n: n["value"])
        out.append(f"{top['label']} carries the largest open exposure at "
                   f"Rs {top['value']/100:,.0f} across {top['meta']['open_invoices']} invoices.")
        worst = max(cust, key=lambda n: n["meta"]["overdue_paise"])
        if worst["meta"]["overdue_paise"] > 0:
            out.append(f"{worst['label']} has the most overdue money at "
                       f"Rs {worst['meta']['overdue_paise']/100:,.0f}.")
    sup = [n for n in nodes if n["type"] == "supplier"]
    if sup:
        tops = max(sup, key=lambda n: n["value"])
        out.append(f"{tops['label']} is the largest open payable at "
                   f"Rs {tops['value']/100:,.0f}.")
    out.append(conc["interpretation"])
    return out
