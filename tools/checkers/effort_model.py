"""Validate Bob-authored WBS rows and serialize a reconciled, unpriced CSV."""

from __future__ import annotations

import csv
from decimal import Decimal
import hashlib
from io import StringIO
import re


FIELDS = (
    "deliverable_id", "wbs_id", "task_name", "role", "quantity", "unit",
    "low_hours", "central_hours", "high_hours", "method",
    "evidence_or_comparable", "uncertainty_driver", "included", "status", "notes",
)
BANDS = ("low_hours", "central_hours", "high_hours")
TEXT_FIELDS = set(FIELDS) - set(BANDS) - {"quantity", "included", "status", "wbs_id"}
NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?\Z")
WBS_ID = re.compile(r"WBS-[0-9]+\.[0-9]+\Z")
FORECAST_STATUSES = {"forecast", "assessment-forecast", "pilot-future-forecast", "future-forecast"}


def _decimal(value: str, field: str, index: int) -> Decimal:
    if not NUMBER.fullmatch(value):
        raise ValueError(f"row {index} {field} must be a nonnegative finite decimal string (up to 12 whole and 6 fractional digits)")
    return Decimal(value)


def _show(value: Decimal) -> str:
    return format(value, "f")


def _totals(rows: list[dict[str, str]]) -> dict[str, str]:
    return {band: _show(sum((Decimal(row[band]) for row in rows), Decimal(0))) for band in BANDS}


def _role_totals(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {role: _totals([row for row in rows if row["role"] == role]) for role in sorted({row["role"] for row in rows})}


def prepare_effort_csv(rows: object) -> dict:
    """Return CSV and exact totals; input rows are never changed or persisted."""
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("rows must be an array of 1 to 100 WBS objects")
    seen: set[str] = set()
    checked: list[dict[str, str]] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != set(FIELDS):
            raise ValueError(f"row {index} must contain exactly the 15 WBS fields")
        for field in FIELDS:
            value = row[field]
            if type(value) is not str or len(value) > 500 or "\x00" in value:
                raise ValueError(f"row {index} {field} must be text of at most 500 characters")
            if field != "notes" and not value.strip():
                raise ValueError(f"row {index} {field} must not be empty")
            if field in TEXT_FIELDS and value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@")):
                raise ValueError(f"row {index} {field} starts with a spreadsheet formula prefix")
        ident = row["wbs_id"]
        if not WBS_ID.fullmatch(ident) or ident in seen:
            raise ValueError(f"row {index} wbs_id must be unique and look like WBS-1.1")
        seen.add(ident)
        _decimal(row["quantity"], "quantity", index)
        values = [_decimal(row[band], band, index) for band in BANDS]
        if not values[0] <= values[1] <= values[2]:
            raise ValueError(f"row {index} hours must satisfy low <= central <= high")
        if row["included"] not in {"included", "excluded"}:
            raise ValueError(f"row {index} included must be included or excluded")
        if row["status"] not in FORECAST_STATUSES:
            raise ValueError(f"row {index} status must be an explicit forecast status; actuals require separately verified evidence")
        checked.append(row)

    included = [row for row in checked if row["included"] == "included"]
    excluded = [row for row in checked if row["included"] == "excluded"]
    future = [row for row in included if row["status"] == "future-forecast"]
    assessment_pilot = [row for row in included if row["status"] in {"assessment-forecast", "pilot-future-forecast"}]
    summaries: list[dict[str, object]] = []
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(checked)

    def summary(label: str, scope: str, source: list[dict[str, str]]) -> None:
        totals = _totals(source)
        writer.writerow({"task_name": label, **totals})
        summaries.append({"label": label, "scope": scope, "wbs_ids": [row["wbs_id"] for row in source], "person_hours": totals})

    summary("GRAND TOTAL ALL INCLUDED", "included", included)
    if excluded:
        # The independent report checker resolves optional scope from explicit WBS IDs.
        ids = " ".join(row["wbs_id"].removeprefix("WBS-") for row in excluded)
        summary(f"EXCLUDED TOTAL {ids}", "excluded", excluded)
    if future:
        summary("FUTURE FORECAST TOTAL", "included future-forecast", future)
    if assessment_pilot:
        summary("ASSESSMENT+PILOT TOTAL", "included assessment/pilot forecast", assessment_pilot)

    csv_text = output.getvalue()
    return {
        "csv": csv_text,
        "sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "row_count": len(checked),
        "source_hours_basis": "total_person_hours_per_row_not_quantity_multiplier",
        "scenario_person_hours": {"included": _totals(included), "excluded": _totals(excluded)},
        "role_person_hours": {"included": _role_totals(included), "excluded": _role_totals(excluded)},
        "summary_rows": summaries,
        "pricing_status": "unpriced",
        "binding_status": "synthetic_nonbinding",
        "validation": "Structure, decimal ranges, forecast status and CSV serialization checked; estimates and evidence remain Bob-authored claims requiring review.",
    }
