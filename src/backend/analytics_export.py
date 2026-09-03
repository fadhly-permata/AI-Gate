"""CSV serialization for the usage/analytics report (post-backlog: the
"laporan bulanan" export gap from PRD §2.4.3).

Pure service layer (NO FastAPI here — layering per be-dev-skill): it turns the
``backend.usage.analytics()`` dict into a spreadsheet-friendly CSV string using
ONLY the stdlib ``csv`` / ``io`` modules. Termux / pure-Python constraint: no
third-party CSV or PDF dependency is introduced.

CSV layout (contract for fe-dev — a single consistent 7-column shape; column 1
is the section tag so every data row shares the same meaning)::

    aigate report,<range>,<group_by>,<generated_at ISO>
    # totals
    section,key,requests,tokens_in,tokens_out,cost_est,saved_tokens_est
    totals,,<requests>,<tokens_in>,<tokens_out>,<cost_est>,<saved_tokens_est>
    # by_group
    by_group,<key>,<requests>,<tokens_in>,<tokens_out>,<cost_est>,<saved_tokens_est>
    ... (one row per group, in ``analytics`` order: requests desc, key asc)
    # buckets
    bucket,<label>,<requests>,<tokens_in>,<tokens_out>,<cost_est>,<saved_tokens_est>
    ... (one row per bucket, chronological ascending)

The ``# totals`` / ``# by_group`` / ``# buckets`` lines are human-readable
section markers; the ``section,key,...`` header row appears once and defines the
7 columns shared by the ``totals`` / ``by_group`` / ``bucket`` data rows.

Empty data still yields a VALID document (metadata + header + a zero ``totals``
row + zero ``bucket`` rows); it is never an error. Rule R12: this module raises
on malformed input rather than swallowing — the router logs + maps to a 500.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Dict, List

# Only ``csv`` is supported today (PDF/other formats deliberately out of scope:
# pure-Python / no-new-dependency constraint).
VALID_FORMATS = ("csv",)
DEFAULT_FORMAT = "csv"

# The single 7-column header shared by every data row (column 1 = section tag).
CSV_COLUMNS = (
    "section",
    "key",
    "requests",
    "tokens_in",
    "tokens_out",
    "cost_est",
    "saved_tokens_est",
)


def _as_int(value: Any) -> int:
    """Coerce a counter field to ``int`` (None/blank -> 0)."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_cost(value: Any) -> float:
    """Coerce a cost field to a clean ``float`` (None/blank -> 0.0, 8dp)."""
    try:
        return round(float(value or 0.0), 8)
    except (TypeError, ValueError):
        return 0.0


def _data_row(section: str, key: str, row: Dict[str, Any]) -> List[Any]:
    """Build one 7-column data row from an analytics dict entry."""
    return [
        section,
        key,
        _as_int(row.get("requests")),
        _as_int(row.get("tokens_in")),
        _as_int(row.get("tokens_out")),
        _as_cost(row.get("cost_est")),
        _as_int(row.get("saved_tokens_est")),
    ]


def build_report_csv(report: Dict[str, Any], generated_at: datetime) -> str:
    """Serialize a ``backend.usage.analytics()`` dict into a CSV document.

    ``generated_at`` is a naive-UTC ``datetime`` supplied by the caller so the
    metadata timestamp and the download filename share one instant. Raises on
    a genuinely malformed ``report`` (missing keys are tolerated as zeros); the
    router catches, logs (``log_error_exc``) and returns a 500 envelope.
    """
    rng = report.get("range", "") or ""
    gb = report.get("group_by", "") or ""
    totals = report.get("totals") or {}
    by_group: List[Dict[str, Any]] = report.get("by_group") or []
    buckets: List[Dict[str, Any]] = report.get("buckets") or []

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Metadata line (4 fields: tag, range, group_by, generated_at ISO).
    writer.writerow(["aigate report", rng, gb, generated_at.isoformat()])

    # # totals block: marker + the single shared header + the totals row.
    writer.writerow(["# totals"])
    writer.writerow(list(CSV_COLUMNS))
    writer.writerow(_data_row("totals", "", totals))

    # # by_group block: marker + one row per group.
    writer.writerow(["# by_group"])
    for group in by_group:
        writer.writerow(_data_row("by_group", str(group.get("key", "")), group))

    # # buckets block: marker + one row per time bucket.
    writer.writerow(["# buckets"])
    for bucket in buckets:
        writer.writerow(_data_row("bucket", str(bucket.get("label", "")), bucket))

    return buf.getvalue()


__all__ = [
    "VALID_FORMATS",
    "DEFAULT_FORMAT",
    "CSV_COLUMNS",
    "build_report_csv",
]
