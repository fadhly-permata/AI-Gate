"""Quota & usage tracking service (B5.5 / PRD §2.4.2 / FSD §2.4.2).

Service layer between the ORM (``UsageRecord`` / ``Provider``) and its
consumers: ``backend.usage_router`` (``GET /api/usage``, ``GET /api/quota``),
the gateway success path (``record_usage_from_result``) and
``backend.combo_routing.quota_aware_order``. No FastAPI here (layering).

Cost estimation
---------------
``estimate_cost`` uses a small built-in ``PRICE_PER_1K`` table — USD per 1k
tokens, ``(in_rate, out_rate)`` — best-effort public list prices. Exact
numbers are NOT critical (this is an estimate, PRD §2.4.2 "Estimasi Biaya").
Lookup order:

1. optional override from the ``Setting`` key ``cost_rates`` (config-in-DB,
   ADR-010/R11): a JSON object ``{"<model>": [in_rate, out_rate], ...}``;
2. exact (case-insensitive) model match in ``PRICE_PER_1K``;
3. longest-prefix match (``gpt-4o-2024-11-20`` -> ``gpt-4o``);
4. unknown model -> ``0.0``.

Quota windows
-------------
``quota_status`` uses CALENDAR-aligned windows so the UI can show a real
countdown (PRD §2.4.2 "hitung mundur reset"):

* ``hour``  -> top of the current hour (UTC);
* ``day``   -> today 00:00 (UTC);
* ``week``  -> Monday 00:00 (UTC).

``reset_at = window_start + window``. A provider without ``quota_limit`` is
INCLUDED with ``remaining=None`` / ``unlimited=True`` (its ``used`` is still
reported over the default ``day`` window) — friendlier for the dashboard than
silently dropping providers. All timestamps are naive UTC (``datetime.utcnow``)
matching the rest of the schema.

Rule R12 / ADR-011: every failure path logs to ``LogEntry`` via ``backend.log``;
no ``except: pass``. Recording is fail-open by contract (gateway must never
break because telemetry failed).
"""

from __future__ import annotations

import bisect
import builtins
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.config import db as _db
from backend.config.settings import get as _setting_get
from backend.log import log_error_exc, log_warning, log_warning_exc
from backend.models import Provider, UsageRecord

LOG_SOURCE = "backend.usage"

# --------------------------------------------------------------------------- #
# Cost model — USD per 1k tokens: {model_prefix: (input_rate, output_rate)}.
# Best-effort public list prices (approximate; estimates only). Unknown model
# -> cost 0.0. Overridable via Setting key ``cost_rates`` (JSON).
# --------------------------------------------------------------------------- #
PRICE_PER_1K: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4.1": (0.002, 0.008),
    "gpt-4.1-mini": (0.0004, 0.0016),
    "gpt-4.1-nano": (0.0001, 0.0004),
    "o3-mini": (0.0011, 0.0044),
    # Anthropic
    "claude-3-5-sonnet": (0.003, 0.015),
    "claude-3-5-haiku": (0.0008, 0.004),
    "claude-3-opus": (0.015, 0.075),
    # Google
    "gemini-2.0-flash": (0.0001, 0.0004),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-1.5-flash": (0.000075, 0.0003),
    # DeepSeek (also reachable via openrouter-style ids)
    "deepseek-chat": (0.00027, 0.0011),
    "deepseek-reasoner": (0.00055, 0.00219),
}

# ``summarize`` / ``GET /api/usage`` rolling windows (FSD: day=last 24h...).
RANGE_WINDOWS: Dict[str, timedelta] = {
    "day": timedelta(hours=24),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
}
DEFAULT_RANGE = "day"

# B5.6 / PRD §2.4.3 ``analytics``: range -> (bucket unit, bucket count).
# day = 24 hourly buckets (last 24h), week = 7 daily, month = 30 daily.
ANALYTICS_BUCKETS: Dict[str, Tuple[str, int]] = {
    "day": ("hour", 24),
    "week": ("day", 7),
    "month": ("day", 30),
}
VALID_GROUP_BY = ("provider", "model")
DEFAULT_GROUP_BY = "model"

# ``quota_status`` calendar-aligned windows (PRD §2.4.2 hour/day/week).
QUOTA_WINDOWS: Dict[str, timedelta] = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(days=7),
}
DEFAULT_QUOTA_WINDOW = "day"


# --------------------------------------------------------------------------- #
# Cost estimation
# --------------------------------------------------------------------------- #
def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Estimated USD cost for a request; ``0.0`` for unknown models.

    Rates come from the optional ``cost_rates`` Setting (JSON), else the
    built-in ``PRICE_PER_1K`` table (exact then longest-prefix match,
    case-insensitive). Bad token counts degrade to 0 (logged), never raise.
    """
    rates = _resolve_rates(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    try:
        ti = max(int(tokens_in or 0), 0)
        to = max(int(tokens_out or 0), 0)
    except (TypeError, ValueError) as exc:  # defensive: bad telemetry input
        log_warning_exc(
            "estimate_cost: invalid token counts; recording cost 0.0",
            source=LOG_SOURCE,
            exc=exc,
            context={"model": model, "tokens_in": tokens_in, "tokens_out": tokens_out},
        )
        return 0.0
    return round((ti / 1000.0) * in_rate + (to / 1000.0) * out_rate, 8)


def _resolve_rates(model: str) -> Optional[Tuple[float, float]]:
    """Resolve ``(in_rate, out_rate)`` for ``model`` or None when unknown."""
    m = (model or "").strip().lower()
    if not m:
        return None
    table: Dict[str, Tuple[float, float]] = {
        k.lower(): v for k, v in PRICE_PER_1K.items()
    }
    table.update(_load_rate_overrides())
    if m in table:
        return table[m]
    # Longest-prefix match (e.g. 'gpt-4o-2024-11-20' -> 'gpt-4o').
    best: Optional[str] = None
    for key in table:
        if m.startswith(key) and (best is None or len(key) > len(best)):
            best = key
    return table[best] if best is not None else None


def _load_rate_overrides() -> Dict[str, Tuple[float, float]]:
    """Parse the optional ``cost_rates`` Setting (fail-open to {})."""
    try:
        raw = _setting_get("cost_rates")
    except Exception as exc:  # noqa: BLE001 - settings lookup must not break cost
        log_warning_exc(
            "cost_rates setting lookup failed; using built-in defaults",
            source=LOG_SOURCE,
            exc=exc,
        )
        return {}
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as exc:
        log_warning(
            f"cost_rates setting is not valid JSON; ignoring it: {exc}",
            source=LOG_SOURCE,
        )
        return {}
    out: Dict[str, Tuple[float, float]] = {}
    if not isinstance(parsed, dict):
        log_warning(
            "cost_rates setting is not a JSON object; ignoring it",
            source=LOG_SOURCE,
        )
        return out
    for key, val in parsed.items():
        try:
            if isinstance(val, dict):
                pair = (float(val["in"]), float(val["out"]))
            else:
                pair = (float(val[0]), float(val[1]))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            log_warning(
                f"ignoring malformed cost_rates entry {key!r}: {exc}",
                source=LOG_SOURCE,
            )
            continue
        out[str(key).lower()] = pair
    return out


# --------------------------------------------------------------------------- #
# Recording (gateway success path) — fail-open by contract
# --------------------------------------------------------------------------- #
def record_usage(
    endpoint_id: Optional[int],
    provider_id: Optional[int],
    account_id: Optional[int],
    model: str,
    tokens_in: int,
    tokens_out: int,
    session: Optional[Session] = None,
    saved_tokens_est: Optional[int] = None,
) -> Optional[UsageRecord]:
    """Persist one ``UsageRecord`` with ``cost_est`` from :func:`estimate_cost`.

    ``saved_tokens_est`` (B5.6 / PRD §2.4.3): estimated tokens saved by the
    Endpoint's Token Saver hook — NULL when no saver was applied (not
    measured), an int (possibly 0) when one was. Fail-open: any error is
    logged (``log_error_exc``) and ``None`` returned — the gateway client
    response must never break because telemetry failed. Pass ``session`` to
    join an outer transaction (no commit here); otherwise a short-lived
    ``SessionLocal`` owns and commits the row.
    """
    try:
        if not provider_id:
            log_warning(
                "record_usage: no provider_id to attribute usage to; skipping",
                source=LOG_SOURCE,
                context={
                    "endpoint_id": endpoint_id,
                    "account_id": account_id,
                    "model": model,
                },
            )
            return None
        cost = estimate_cost(model, tokens_in, tokens_out)
        own = session is None
        s: Session = session if session is not None else _db.SessionLocal()
        try:
            row = UsageRecord(
                endpoint_id=endpoint_id,
                provider_id=int(provider_id),
                account_id=int(account_id) if account_id is not None else None,
                model=model or "",
                tokens_in=int(tokens_in or 0),
                tokens_out=int(tokens_out or 0),
                cost_est=cost,
                saved_tokens_est=(
                    int(saved_tokens_est) if saved_tokens_est is not None else None
                ),
                ts=datetime.utcnow(),
            )
            s.add(row)
            s.flush()
            if own:
                s.commit()
                # Re-load attributes while still attached (commit expires them;
                # after ``close()`` below the caller could not refresh them).
                s.refresh(row)
            return row
        except Exception:
            if own:
                s.rollback()
            raise
        finally:
            if own:
                s.close()
    except Exception as exc:  # noqa: BLE001 - fail-open mandated (B5.5)
        log_error_exc(
            "record_usage failed (fail-open; client response unaffected)",
            source=LOG_SOURCE,
            exc=exc,
            context={
                "endpoint_id": endpoint_id,
                "provider_id": provider_id,
                "account_id": account_id,
                "model": model,
            },
        )
        return None


def record_usage_from_result(
    result: Any,
    provider_id: Optional[int],
    account_id: Optional[int],
    model: str,
    endpoint_id: Optional[int] = None,
    session: Optional[Session] = None,
    saved_tokens_est: Optional[int] = None,
) -> Optional[UsageRecord]:
    """Extract ``usage`` from an OpenAI-shaped response dict and record it.

    Missing/unparseable ``usage`` degrades to 0/0 tokens (logged warning), not
    an exception. ``saved_tokens_est`` is threaded through to
    :func:`record_usage` unchanged (B5.6; NULL = saver not applied). Returns
    the persisted row (or None on any failure).
    """
    tokens_in, tokens_out = 0, 0
    try:
        usage = (result or {}).get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or 0)
        tokens_out = int(usage.get("completion_tokens") or 0)
    except (AttributeError, TypeError, ValueError) as exc:
        log_warning_exc(
            "could not parse usage from upstream response; recording 0 tokens",
            source=LOG_SOURCE,
            exc=exc,
            context={"provider_id": provider_id, "model": model},
        )
    return record_usage(
        endpoint_id=endpoint_id,
        provider_id=provider_id,
        account_id=account_id,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        session=session,
        saved_tokens_est=saved_tokens_est,
    )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def since_for_range(range_key: str) -> datetime:
    """Rolling window start for ``day|week|month`` (default ``day``)."""
    delta = RANGE_WINDOWS.get((range_key or DEFAULT_RANGE).lower())
    if delta is None:
        delta = RANGE_WINDOWS[DEFAULT_RANGE]
    return datetime.utcnow() - delta


def summarize(
    session: Session,
    provider_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    range: str = DEFAULT_RANGE,
) -> dict:
    """Aggregate UsageRecords within the rolling window into a summary dict.

    Shape (consumed by ``GET /api/usage/summary``)::

        {
          "object": "usage_summary",
          "range": "day",
          "since": "<iso>",
          "totals": {"requests", "tokens_in", "tokens_out", "cost_est"},
          "by_provider": [{"provider_id", "provider_name", "requests",
                           "tokens_in", "tokens_out", "cost_est"}, ...],
          "by_model":    [{"model", "requests", "tokens_in", "tokens_out",
                           "cost_est"}, ...]
        }
    """
    rng = (range or DEFAULT_RANGE).lower()
    since = since_for_range(rng)
    q = session.query(UsageRecord).filter(UsageRecord.ts >= since)
    if provider_id is not None:
        q = q.filter(UsageRecord.provider_id == provider_id)
    if endpoint_id is not None:
        q = q.filter(UsageRecord.endpoint_id == endpoint_id)
    rows = q.all()

    totals = {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost_est": 0.0}
    by_prov: Dict[int, Dict[str, Any]] = {}
    by_model: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        totals["requests"] += 1
        totals["tokens_in"] += int(r.tokens_in or 0)
        totals["tokens_out"] += int(r.tokens_out or 0)
        totals["cost_est"] += float(r.cost_est or 0.0)
        prov = by_prov.setdefault(
            r.provider_id,
            {
                "provider_id": r.provider_id,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_est": 0.0,
            },
        )
        prov["requests"] += 1
        prov["tokens_in"] += int(r.tokens_in or 0)
        prov["tokens_out"] += int(r.tokens_out or 0)
        prov["cost_est"] += float(r.cost_est or 0.0)
        mdl = by_model.setdefault(
            r.model or "",
            {"model": r.model or "", "requests": 0, "tokens_in": 0,
             "tokens_out": 0, "cost_est": 0.0},
        )
        mdl["requests"] += 1
        mdl["tokens_in"] += int(r.tokens_in or 0)
        mdl["tokens_out"] += int(r.tokens_out or 0)
        mdl["cost_est"] += float(r.cost_est or 0.0)

    totals["cost_est"] = round(totals["cost_est"], 8)
    names: Dict[int, str] = {}
    if by_prov:
        for p in session.query(Provider).filter(
            Provider.id.in_(list(by_prov.keys()))
        ).all():
            names[p.id] = p.name
    by_provider = []
    for pid in sorted(by_prov):
        entry = by_prov[pid]
        entry["cost_est"] = round(entry["cost_est"], 8)
        entry["provider_name"] = names.get(pid, "")
        by_provider.append(entry)
    by_model_list = []
    for key in sorted(by_model):
        entry = by_model[key]
        entry["cost_est"] = round(entry["cost_est"], 8)
        by_model_list.append(entry)

    return {
        "object": "usage_summary",
        "range": rng,
        "since": since.isoformat(),
        "totals": totals,
        "by_provider": by_provider,
        "by_model": by_model_list,
    }


# --------------------------------------------------------------------------- #
# Usage Analytics (B5.6 / PRD §2.4.3 / FSD §2.4.3 — token & usage TRENDS)
# --------------------------------------------------------------------------- #
def saved_tokens_from_bytes(saved_bytes: Optional[int]) -> int:
    """Rough token heuristic: ``saved_bytes // 4`` (≈4 bytes/token), floored ≥0.

    Used by the gateway to convert the RTK byte-savings estimate into the
    ``saved_tokens_est`` figure aggregated by :func:`analytics`. Output-side
    savers (caveman/ponytail) are not measurable pre-request and record 0.
    """
    try:
        return max(0, int(saved_bytes or 0) // 4)
    except (TypeError, ValueError) as exc:  # defensive: bad telemetry input
        log_warning_exc(
            "saved_tokens_from_bytes: invalid input; using 0",
            source=LOG_SOURCE,
            exc=exc,
            context={"saved_bytes": saved_bytes},
        )
        return 0


def _bucket_start(dt: datetime, unit: str) -> datetime:
    """Calendar-aligned start of the bucket containing ``dt`` (naive UTC)."""
    if unit == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_label(dt: datetime, unit: str) -> str:
    """Bucket label: hourly ``YYYY-MM-DD HH:00``, daily ``YYYY-MM-DD``."""
    if unit == "hour":
        return dt.strftime("%Y-%m-%d %H:00")
    return dt.strftime("%Y-%m-%d")


def analytics(
    session: Session,
    range: str = DEFAULT_RANGE,
    group_by: str = DEFAULT_GROUP_BY,
) -> dict:
    """Token/usage trends over time buckets + totals + per-group breakdown.

    Shape (consumed by ``GET /api/analytics`` — the fe-dev contract)::

        {
          "object": "analytics",
          "range": "month", "group_by": "model",
          "buckets": [{"label": "2026-09-01", "requests": N, "tokens_in": X,
                       "tokens_out": Y, "cost_est": Z, "saved_tokens_est": S}, ...],
          "totals":  {"requests", "tokens_in", "tokens_out", "cost_est",
                      "saved_tokens_est"},
          "by_group": [{"key": "gpt-4o", "requests", "tokens_in", "tokens_out",
                        "cost_est", "saved_tokens_est"}, ...]
        }

    Bucketing (documented decision): ``day`` -> 24 HOURLY buckets ending at the
    current hour; ``week`` -> 7 DAILY buckets ending today; ``month`` -> 30
    DAILY buckets ending today. Empty buckets are INCLUDED as zeros so the UI
    can chart a continuous trend. Labels are naive-UTC strings (see
    :func:`_bucket_label`), buckets chronological ascending.

    ``group_by=provider`` keys on the provider NAME (a row whose provider is
    missing falls back to ``"provider#<id>"``); ``group_by=model`` keys on
    ``UsageRecord.model``. ``by_group`` is sorted by requests desc, key asc.
    Rows with ``saved_tokens_est`` NULL (no saver applied) contribute 0.
    """
    rng = (range or DEFAULT_RANGE).lower()
    if rng not in ANALYTICS_BUCKETS:
        rng = DEFAULT_RANGE
    gb = (group_by or DEFAULT_GROUP_BY).lower()
    if gb not in VALID_GROUP_BY:
        gb = DEFAULT_GROUP_BY

    unit, count = ANALYTICS_BUCKETS[rng]
    delta = timedelta(hours=1) if unit == "hour" else timedelta(days=1)
    now = datetime.utcnow()
    last_start = _bucket_start(now, unit)
    # NOTE: the ``range`` parameter shadows the builtin (API parity with
    # ``summarize``) — use ``builtins.range`` for the bucket offsets.
    starts = [last_start - delta * i for i in builtins.range(count)]
    starts.reverse()
    since = starts[0]

    rows = session.query(UsageRecord).filter(UsageRecord.ts >= since).all()

    buckets = [
        {
            "label": _bucket_label(s, unit),
            "requests": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_est": 0.0,
            "saved_tokens_est": 0,
        }
        for s in starts
    ]
    totals = {
        "requests": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_est": 0.0,
        "saved_tokens_est": 0,
    }
    groups: Dict[str, Dict[str, Any]] = {}

    names: Dict[int, str] = {}
    if gb == "provider" and rows:
        pids = {r.provider_id for r in rows if r.provider_id is not None}
        if pids:
            for p in session.query(Provider).filter(
                Provider.id.in_(list(pids))
            ).all():
                names[p.id] = p.name

    for r in rows:
        ti = int(r.tokens_in or 0)
        to = int(r.tokens_out or 0)
        cost = float(r.cost_est or 0.0)
        saved = int(r.saved_tokens_est or 0)
        idx = min(max(bisect.bisect_right(starts, r.ts) - 1, 0), count - 1)
        b = buckets[idx]
        b["requests"] += 1
        b["tokens_in"] += ti
        b["tokens_out"] += to
        b["cost_est"] += cost
        b["saved_tokens_est"] += saved
        totals["requests"] += 1
        totals["tokens_in"] += ti
        totals["tokens_out"] += to
        totals["cost_est"] += cost
        totals["saved_tokens_est"] += saved
        if gb == "provider":
            key = names.get(r.provider_id) or f"provider#{r.provider_id}"
        else:
            key = r.model or ""
        g = groups.setdefault(
            key,
            {
                "key": key,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_est": 0.0,
                "saved_tokens_est": 0,
            },
        )
        g["requests"] += 1
        g["tokens_in"] += ti
        g["tokens_out"] += to
        g["cost_est"] += cost
        g["saved_tokens_est"] += saved

    for b in buckets:
        b["cost_est"] = round(b["cost_est"], 8)
    totals["cost_est"] = round(totals["cost_est"], 8)
    by_group = sorted(groups.values(), key=lambda g: (-g["requests"], g["key"]))
    for g in by_group:
        g["cost_est"] = round(g["cost_est"], 8)

    return {
        "object": "analytics",
        "range": rng,
        "group_by": gb,
        "buckets": buckets,
        "totals": totals,
        "by_group": by_group,
    }


# --------------------------------------------------------------------------- #
# Quota status (real-time remaining + reset countdown)
# --------------------------------------------------------------------------- #
def _window_start(now: datetime, window: str) -> datetime:
    """Calendar-aligned start of the current quota window (naive UTC)."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if window == "hour":
        return now.replace(minute=0, second=0, microsecond=0)
    if window == "week":
        return midnight - timedelta(days=midnight.weekday())  # Monday 00:00
    return midnight  # 'day' (and any invalid value -> day)


def _window_delta(window: str) -> timedelta:
    return QUOTA_WINDOWS.get(window, QUOTA_WINDOWS[DEFAULT_QUOTA_WINDOW])


def quota_status(
    session: Session, provider_id: Optional[int] = None
) -> List[dict]:
    """Per-provider quota state for ``GET /api/quota`` + quota-aware routing.

    One entry per provider (optionally filtered by ``provider_id``)::

        {
          "provider_id": 1, "provider_name": "sub", "tier": "subscription",
          "quota_limit": 100000 | null,   # null = unlimited
          "quota_window": "day",          # hour|day|week (default day)
          "used": 12345,                  # tokens_in+out within current window
          "remaining": 87655 | null,      # null when unlimited
          "unlimited": false,
          "window_start": "<iso>", "reset_at": "<iso>",
          "seconds_to_reset": 43210,      # countdown for the UI
          "cost_est": 0.123               # USD estimate within current window
        }

    Providers WITHOUT ``quota_limit`` are included with ``remaining=None`` /
    ``unlimited=True`` (documented decision — see module docstring).
    """
    now = datetime.utcnow()
    q = session.query(Provider)
    if provider_id is not None:
        q = q.filter(Provider.id == provider_id)
    out: List[dict] = []
    for p in q.order_by(Provider.id.asc()).all():
        window = (p.quota_window or DEFAULT_QUOTA_WINDOW).lower()
        if window not in QUOTA_WINDOWS:
            window = DEFAULT_QUOTA_WINDOW
        start = _window_start(now, window)
        used, cost = _used_and_cost_in_window(session, p.id, start)
        limit = p.quota_limit
        unlimited = limit is None
        remaining = None if unlimited else max(0, int(limit) - used)
        reset_at = start + _window_delta(window)
        out.append(
            {
                "provider_id": p.id,
                "provider_name": p.name,
                "tier": p.tier or "subscription",
                "quota_limit": limit,
                "quota_window": window,
                "used": used,
                "remaining": remaining,
                "unlimited": unlimited,
                "window_start": start.isoformat(),
                "reset_at": reset_at.isoformat(),
                "seconds_to_reset": max(
                    0, int((reset_at - now).total_seconds())
                ),
                "cost_est": round(cost, 8),
            }
        )
    return out


def _used_and_cost_in_window(
    session: Session, provider_id: int, start: datetime
) -> Tuple[int, float]:
    """Sum (tokens_in+tokens_out) and cost_est for ``provider_id`` since ``start``."""
    from sqlalchemy import func

    row = (
        session.query(
            func.coalesce(func.sum(UsageRecord.tokens_in + UsageRecord.tokens_out), 0),
            func.coalesce(func.sum(UsageRecord.cost_est), 0.0),
        )
        .filter(UsageRecord.provider_id == provider_id)
        .filter(UsageRecord.ts >= start)
        .one()
    )
    return int(row[0] or 0), float(row[1] or 0.0)


__all__ = [
    "PRICE_PER_1K",
    "RANGE_WINDOWS",
    "QUOTA_WINDOWS",
    "ANALYTICS_BUCKETS",
    "VALID_GROUP_BY",
    "DEFAULT_RANGE",
    "DEFAULT_QUOTA_WINDOW",
    "DEFAULT_GROUP_BY",
    "estimate_cost",
    "record_usage",
    "record_usage_from_result",
    "saved_tokens_from_bytes",
    "since_for_range",
    "summarize",
    "analytics",
    "quota_status",
]
