"""Shared helpers for the API layer."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any

from fastapi import Query

from app.core.money import format_inr, paise_to_rupees


def today_param(as_of: str | None = Query(None, description="ISO date to evaluate as 'today'")) -> date:
    """Every endpoint takes an ``as_of``.

    The demo workspace is generated against a fixed date, and point-in-time
    evaluation is a first-class feature rather than a test hook: the whole
    forecast-accuracy story depends on being able to ask what the engine
    would have said last month.
    """
    return date.fromisoformat(as_of) if as_of else date.today()


def money(paise: int | None) -> dict | None:
    if paise is None:
        return None
    return {"paise": int(paise), "rupees": paise_to_rupees(int(paise)),
            "display": format_inr(int(paise)), "compact": format_inr(int(paise), compact=True)}


def jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "dict") and callable(obj.dict):
        try:
            return jsonable(obj.dict())
        except Exception:
            pass
    return obj
