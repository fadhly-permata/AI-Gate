"""CSV export of the usage/analytics report (post-backlog: PRD §2.4.3 monthly
report gap).

Covers ``GET /api/analytics/export``:
* month + group_by=model -> 200 text/csv, Content-Disposition filename, and the
  totals / by_group / bucket rows carry the SAME numbers as ``GET /api/analytics``
  (CSV parsed back with the stdlib ``csv`` module and asserted);
* group_by=provider works (keys are provider NAMES);
* invalid range / group_by / format -> 400 OpenAI-style envelope;
* empty DB -> 200 valid CSV (metadata + header + zero totals + zero buckets, no
  by_group rows) — never an error;
* defaults (no params) -> range=month, group_by=model;
* the export is logged to ``LogEntry`` (R12).

Hermetic in-memory DB (StaticPool) mirroring test_analytics.py.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.analytics_router as analytics_router
import backend.config.db as db_mod
import backend.usage as usage
from backend.models import LogEntry, Provider, UsageRecord
from backend.server import app


def _make_sessionmaker() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    from backend.config.db import Base

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _patch_db(monkeypatch, sf: sessionmaker) -> None:
    # analytics_router opens its own session; backend.log writes LogEntry rows
    # through the db module binding.
    monkeypatch.setattr(db_mod, "SessionLocal", sf)
    monkeypatch.setattr(analytics_router, "SessionLocal", sf)


@pytest.fixture
def sf(monkeypatch):
    factory = _make_sessionmaker()
    _patch_db(monkeypatch, factory)
    return factory


# --------------------------------------------------------------------------- #
# Seeding + CSV parsing helpers
# --------------------------------------------------------------------------- #
def _seed_provider(sf, name: str) -> int:
    with sf() as session:
        p = Provider(name=name, type="openai", base_url=f"http://{name}.test/v1",
                     api_key="sk-x", enabled=True)
        session.add(p)
        session.commit()
        return p.id


def _seed_rows(sf) -> dict:
    """Two providers, several models across a few days (month window)."""
    p1 = _seed_provider(sf, "alpha")
    p2 = _seed_provider(sf, "beta")
    now = datetime.utcnow()
    with sf() as session:
        session.add_all(
            [
                # Today: 2 gpt-4o rows (one with a saver, one without).
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=100,
                            tokens_out=50, cost_est=0.1, saved_tokens_est=8, ts=now),
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=10,
                            tokens_out=10, cost_est=0.01, saved_tokens_est=None,
                            ts=now),
                # 2 days back: a claude row on provider beta.
                UsageRecord(provider_id=p2, model="claude-3-5-sonnet", tokens_in=20,
                            tokens_out=20, cost_est=0.02, saved_tokens_est=4,
                            ts=now - timedelta(days=2)),
                # 29 days back: first bucket of the 30-day window.
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=1,
                            tokens_out=1, cost_est=0.001, saved_tokens_est=0,
                            ts=now - timedelta(days=29)),
                # 31 days back: OUTSIDE the month window (must not appear).
                UsageRecord(provider_id=p1, model="gpt-4o", tokens_in=999,
                            tokens_out=999, cost_est=9.99, saved_tokens_est=999,
                            ts=now - timedelta(days=31)),
            ]
        )
        session.commit()
    return {"p1": p1, "p2": p2, "now": now}


def _parse_csv(text: str) -> list:
    return list(csv.reader(io.StringIO(text, newline="")))


def _rows_with_tag(rows: list, tag: str) -> list:
    return [r for r in rows if r and r[0] == tag]


# --------------------------------------------------------------------------- #
# month + group_by=model: full round-trip
# --------------------------------------------------------------------------- #
def test_export_csv_month_group_by_model(sf):
    _seed_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics/export?range=month&group_by=model")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    cd = resp.headers["content-disposition"]
    assert cd.startswith("attachment;")
    m = re.search(r'filename="aigate-report-month-(\d{8})\.csv"', cd)
    assert m is not None, cd
    assert m.group(1) == datetime.utcnow().strftime("%Y%m%d")

    rows = _parse_csv(resp.text)

    # Metadata line.
    meta = _rows_with_tag(rows, "aigate report")
    assert len(meta) == 1
    assert meta[0] == ["aigate report", "month", "model", meta[0][3]]
    # generated_at parses as ISO.
    datetime.fromisoformat(meta[0][3])

    # Header row appears exactly once and defines the 7 columns.
    header = _rows_with_tag(rows, "section")
    assert header == [
        ["section", "key", "requests", "tokens_in", "tokens_out",
         "cost_est", "saved_tokens_est"]
    ]

    # Totals row (key column empty) matches the analytics totals.
    totals = _rows_with_tag(rows, "totals")
    assert len(totals) == 1
    assert totals[0] == ["totals", "", "4", "131", "81", "0.131", "12"]

    # by_group rows: gpt-4o (3 req) then claude (1 req), requests desc.
    by_group = _rows_with_tag(rows, "by_group")
    assert [r[1] for r in by_group] == ["gpt-4o", "claude-3-5-sonnet"]
    assert by_group[0] == ["by_group", "gpt-4o", "3", "111", "61", "0.111", "8"]
    assert by_group[1] == [
        "by_group", "claude-3-5-sonnet", "1", "20", "20", "0.02", "4"
    ]

    # buckets: 30 daily rows, chronological, zeros except the seeded days.
    buckets = _rows_with_tag(rows, "bucket")
    assert len(buckets) == 30
    assert buckets[0][1] == (datetime.utcnow() - timedelta(days=29)).strftime("%Y-%m-%d")
    assert buckets[-1][1] == datetime.utcnow().strftime("%Y-%m-%d")
    # Today bucket: 2 requests, saved 8.
    assert buckets[-1] == [
        "bucket", buckets[-1][1], "2", "110", "60", "0.11", "8"
    ]
    # First bucket (29 days back): 1 request.
    assert buckets[0][2] == "1"
    # A known-empty middle bucket is all zeros.
    assert buckets[10] == [
        "bucket", buckets[10][1], "0", "0", "0", "0.0", "0"
    ]

    # Section markers present, in order.
    tags = [r[0] for r in rows if r and r[0].startswith("#")]
    assert tags == ["# totals", "# by_group", "# buckets"]


def test_export_matches_analytics_json(sf):
    """CSV numbers must equal the JSON analytics endpoint (single source)."""
    _seed_rows(sf)
    client = TestClient(app)
    js = client.get("/api/analytics?range=month&group_by=model").json()
    resp = client.get("/api/analytics/export?range=month&group_by=model")
    rows = _parse_csv(resp.text)
    totals = _rows_with_tag(rows, "totals")[0]
    assert int(totals[2]) == js["totals"]["requests"]
    assert int(totals[3]) == js["totals"]["tokens_in"]
    assert int(totals[4]) == js["totals"]["tokens_out"]
    assert float(totals[5]) == pytest.approx(js["totals"]["cost_est"])
    assert int(totals[6]) == js["totals"]["saved_tokens_est"]
    by_group = {r[1]: r for r in _rows_with_tag(rows, "by_group")}
    for g in js["by_group"]:
        assert int(by_group[g["key"]][2]) == g["requests"]


# --------------------------------------------------------------------------- #
# group_by=provider
# --------------------------------------------------------------------------- #
def test_export_csv_group_by_provider(sf):
    _seed_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics/export?range=month&group_by=provider")
    assert resp.status_code == 200
    assert 'filename="aigate-report-month-' in resp.headers["content-disposition"]
    rows = _parse_csv(resp.text)
    keys = {r[1] for r in _rows_with_tag(rows, "by_group")}
    # provider NAMES (alpha has 3 rows, beta has 1).
    assert keys == {"alpha", "beta"}
    by_group = {r[1]: r for r in _rows_with_tag(rows, "by_group")}
    assert by_group["alpha"][2] == "3"
    assert by_group["beta"][2] == "1"


# --------------------------------------------------------------------------- #
# defaults
# --------------------------------------------------------------------------- #
def test_export_defaults_month_model(sf):
    _seed_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics/export")
    assert resp.status_code == 200
    rows = _parse_csv(resp.text)
    meta = _rows_with_tag(rows, "aigate report")[0]
    assert meta[1] == "month"
    assert meta[2] == "model"
    assert 'aigate-report-month-' in resp.headers["content-disposition"]


# --------------------------------------------------------------------------- #
# validation -> 400 OpenAI-style envelope
# --------------------------------------------------------------------------- #
def test_export_invalid_range_400(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics/export?range=year")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_range"


def test_export_invalid_group_by_400(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics/export?group_by=endpoint")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_group_by"


def test_export_invalid_format_400(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics/export?format=pdf")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_format"


# --------------------------------------------------------------------------- #
# empty DB -> valid CSV, not an error
# --------------------------------------------------------------------------- #
def test_export_empty_db_valid_csv(sf):
    client = TestClient(app)
    resp = client.get("/api/analytics/export?range=month&group_by=model")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    rows = _parse_csv(resp.text)
    # metadata + header + zero totals + 30 zero buckets, no by_group rows.
    assert _rows_with_tag(rows, "totals")[0] == [
        "totals", "", "0", "0", "0", "0.0", "0"
    ]
    assert _rows_with_tag(rows, "by_group") == []
    assert len(_rows_with_tag(rows, "bucket")) == 30
    assert all(int(r[2]) == 0 for r in _rows_with_tag(rows, "bucket"))


# --------------------------------------------------------------------------- #
# R12: the export is logged
# --------------------------------------------------------------------------- #
def test_export_is_logged(sf):
    _seed_rows(sf)
    client = TestClient(app)
    resp = client.get("/api/analytics/export?range=month&group_by=model")
    assert resp.status_code == 200
    with sf() as session:
        msgs = [
            r.message
            for r in session.query(LogEntry)
            .filter_by(source="backend.analytics.router")
            .all()
        ]
    assert any(m.startswith("GET /api/analytics/export") for m in msgs)
