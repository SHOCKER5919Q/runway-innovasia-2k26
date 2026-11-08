from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.common import jsonable, today_param
from app.api.deps import DbDep, Tenant
from app.copilot import llm, tools
from app.copilot.service import SUGGESTIONS, ask
from app.core.security import rate_limiter
from app.models import CopilotMessage

router = APIRouter(prefix="/api/copilot", tags=["copilot"])
AsOf = Annotated[date, Depends(today_param)]


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    language: str = "en"
    use_llm: bool = True


@router.post("/ask")
def copilot_ask(body: AskIn, db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.digital_twin.digital_twin_service import get_bundle
    if not rate_limiter.allow(f"copilot:{ctx.user.id}"):
        raise HTTPException(429, "Too many questions in a short period. Try again shortly.")
    b = get_bundle(db, ctx.business_id, as_of)
    return jsonable(ask(db, b, body.question, conversation_id=body.conversation_id,
                        language=body.language, user_id=ctx.user.id,
                        use_llm=body.use_llm))


@router.get("/history")
def history(db: DbDep, ctx: Tenant, conversation_id: str | None = None,
            limit: int = Query(60, le=300)):
    q = select(CopilotMessage).where(CopilotMessage.business_id == ctx.business_id)
    if conversation_id:
        q = q.where(CopilotMessage.conversation_id == conversation_id)
    rows = db.scalars(q.order_by(CopilotMessage.created_at.desc()).limit(limit)).all()
    rows.reverse()
    return jsonable({"messages": [{
        "id": m.id, "conversation_id": m.conversation_id, "role": m.role,
        "content": m.content, "tool_calls": m.tool_calls_json,
        "evidence": m.evidence_json, "state_refs": m.state_refs_json,
        "generator": m.generator, "language": m.language,
        "created_at": m.created_at.isoformat()} for m in rows]})


@router.get("/suggestions")
def suggestions(db: DbDep, ctx: Tenant, as_of: AsOf):
    from app.digital_twin.digital_twin_service import get_bundle
    b = get_bundle(db, ctx.business_id, as_of, heavy=False)
    tailored = list(SUGGESTIONS)
    if b.behaviour:
        worst = max(b.behaviour, key=lambda c: c.mean_delay_days)
        tailored.insert(1, f"What if {worst.name} pays 30 days late?")
    if b.recommendations:
        tailored.insert(0, f"Explain: {b.recommendations[0].title}")
    return {"suggestions": tailored[:10],
            "languages": [{"code": "en", "label": "English"},
                          {"code": "hi", "label": "हिन्दी"},
                          {"code": "te", "label": "తెలుగు"},
                          {"code": "ta", "label": "தமிழ்"},
                          {"code": "mr", "label": "मराठी"}],
            "llm_available": llm.available(),
            "generator_note": (
                "An Anthropic API key is configured, so answers are written by the model "
                "from deterministic tool output and every rupee figure is verified "
                "against that output before display."
                if llm.available() else
                "No LLM key is configured, so answers are rendered deterministically from "
                "the same tool output. The figures are identical either way - the model "
                "only ever writes the prose.")}


@router.get("/tools")
def tool_schema():
    return {"tools": tools.schema(),
            "architecture": ("question -> deterministic intent routing -> authorised tool "
                             "-> financial engine -> structured result -> explanation."),
            "guarantees": [
                "The language model never calculates a financial figure.",
                "Every rupee amount in a reply is verified against the tool output "
                "before it is shown; an unverified figure causes the reply to be "
                "discarded and the deterministic renderer used instead.",
                "Tools are bound to one business. No tool accepts a business id, so "
                "there is no parameter through which data could cross tenants.",
                "Untrusted text (bank narrations, uploaded documents, counterparty "
                "names) is fenced and declared as data in the system prompt.",
                "Every answer states whether it is actual, predicted or simulated.",
            ]}
