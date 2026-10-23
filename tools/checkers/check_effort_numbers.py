"""Independently reconcile effort-model CSV summary rows and, for factory v2, SOW price figures.

With --sow and --price-table, every figure in the SOW's two commercial sections and any
currency amount anywhere in it must be a value held by the SI engine's illustrative table.
"""

from __future__ import annotations

import argparse
import csv
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


BANDS = ("low_hours", "central_hours", "high_hours")
REQUIRED_FIELDS = {
    "deliverable_id", "wbs_id", "task_name", "role", "quantity", "unit",
    *BANDS, "method", "evidence_or_comparable", "uncertainty_driver",
    "included", "status", "notes",
}


class CheckError(ValueError):
    """Raised when the CSV cannot be reconciled without inference."""


def decimal(value: str, field: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise CheckError(f"invalid {field}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise CheckError(f"invalid {field}: {value!r}")
    return result


def show(value: Decimal) -> str:
    return format(value, "f")


def totals(rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        band: show(sum((decimal(row[band], band) for row in rows), Decimal(0)))
        for band in BANDS
    }


def is_summary(row: dict[str, str]) -> bool:
    return row["task_name"].startswith((
        "GRAND TOTAL ALL INCLUDED", "EXCLUDED TOTAL ", "FUTURE FORECAST TOTAL",
        "ASSESSMENT+PILOT TOTAL",
    ))


def check_csv(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != REQUIRED_FIELDS:
            raise CheckError("CSV must contain exactly the effort-model fields")
        rows = list(reader)

    regular = [row for row in rows if not is_summary(row)]
    summaries = [row for row in rows if is_summary(row)]
    if not regular:
        raise CheckError("CSV has no WBS rows")
    for row in regular:
        if not row["wbs_id"]:
            raise CheckError("WBS row is missing wbs_id")
        if row["included"] not in {"included", "excluded"}:
            raise CheckError(f"invalid inclusion scope for {row['wbs_id']}")
        for band in BANDS:
            decimal(row[band], band)

    expected: dict[str, dict[str, str]] = {
        "GRAND TOTAL ALL INCLUDED": totals([row for row in regular if row["included"] == "included"]),
    }
    excluded = [row for row in regular if row["included"] == "excluded"]
    if excluded:
        expected["EXCLUDED TOTAL"] = totals(excluded)
    future = [row for row in regular if row["included"] == "included" and row["status"] == "future-forecast"]
    if future:
        expected["FUTURE FORECAST TOTAL"] = totals(future)
    assessment_pilot = [
        row for row in regular
        if row["included"] == "included" and row["status"] in {"assessment-forecast", "pilot-future-forecast"}
    ]
    if assessment_pilot:
        expected["ASSESSMENT+PILOT TOTAL"] = totals(assessment_pilot)

    observed: dict[str, dict[str, str]] = {}
    for row in summaries:
        label = next((key for key in expected if row["task_name"].startswith(key)), None)
        if label is None:
            raise CheckError(f"unexpected summary row: {row['task_name']!r}")
        if label in observed:
            raise CheckError(f"duplicate summary row: {label}")
        observed[label] = {band: show(decimal(row[band], band)) for band in BANDS}

    errors = [
        f"{label} expected {values}, observed {observed.get(label)}"
        for label, values in expected.items()
        if observed.get(label) != values
    ]
    return {"passed": not errors, "errors": errors, "wbs_row_count": len(regular), "summary_row_count": len(summaries)}


# Factory v2: the SOW may only reference the SI engine's illustrative table.  Every
# figure in its two commercial sections, and any currency amount anywhere in it, must
# be a value that table actually holds.
SOW_COMMERCIAL_SECTIONS = ("Rate-card roles and risk drivers", "Illustrative price reference")
FIGURE = re.compile(
    r"(?<![\w.\-/$€£])(?P<number>\d[\d,]*(?:\.\d+)?)(?![\w\-/]|\.\d|,\d)"
    r"(?P<unit>\s?(?:%|percent\b|person-hours\b|hours?\b|hrs?\b|h\b|SGD\b))?",
    re.IGNORECASE,
)
CURRENCY_FIGURE = re.compile(
    r"(?i)(?:\b(?:SGD|USD|EUR|GBP|AUD)\s?|(?:\bS|\bUS)?\$\s?|[€£]\s?)(?P<before>\d[\d,]*(?:\.\d+)?)"
    r"|\b(?P<after>\d[\d,]*(?:\.\d+)?)\s?(?:SGD|USD|EUR|GBP|AUD)\b"
)
LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s")


def _section(text: str, heading: str) -> str:
    numbered = r"(?:[0-9]+(?:\.[0-9]+)*(?:\.|)\s+)?"
    match = re.search(rf"(?mi)^##\s+{numbered}{re.escape(heading)}\s*$", text)
    if not match:
        return ""
    following = re.search(r"(?m)^##\s", text[match.end():])
    return text[match.end():match.end() + following.start()] if following else text[match.end():]


def _value(text: str) -> Decimal:
    return decimal(text.replace(",", ""), "SOW figure")


def table_figures(table: dict) -> dict[str, set[Decimal]]:
    """Collect every money, hours and percent value the engine table holds."""
    if not isinstance(table, dict) or table.get("pricing_status") != "illustrative" or table.get("not_a_quote") is not True:
        raise CheckError("price table must be the SI engine's illustrative table labelled not a quote")
    engine = table.get("engine_result")
    if not isinstance(engine, dict) or engine.get("pricing_status") != "illustrative" or not isinstance(engine.get("totals"), dict):
        raise CheckError("price table carries no calculated illustrative engine result")
    money: set[Decimal] = set()
    hours: set[Decimal] = set()
    percent: set[Decimal] = set()
    for line in engine.get("work_packages") or []:
        money.add(decimal(str(line["rate_sgd_per_hour"]), "rate"))
        money.update(decimal(str(value), "subtotal") for value in line["subtotals_sgd"].values())
        hours.update(decimal(str(value), "hours") for value in line["hours"].values())
    for band in engine["totals"].values():
        for key in ("subtotal_sgd", "risk_allowance_sgd", "total_excluding_tax_sgd"):
            money.add(decimal(str(band[key]), key))
        percent.add(decimal(str(band["risk_allowance_percent"]), "risk allowance"))
    hours.update(decimal(str(value), "hours") for value in (engine.get("effort_totals_hours") or {}).values())
    for values in (engine.get("effort_by_role_hours") or {}).values():
        hours.update(decimal(str(value), "hours") for value in values.values())
    return {"money": money, "hours": hours, "percent": percent}


def check_sow_figures(sow_text: str, table: dict) -> list[str]:
    """Return one error per SOW figure that the illustrative engine table does not hold."""
    figures = table_figures(table)
    every = figures["money"] | figures["hours"] | figures["percent"]
    errors: list[str] = []
    for heading in SOW_COMMERCIAL_SECTIONS:
        body = LIST_MARKER.sub(" ", _section(sow_text, heading))
        for match in FIGURE.finditer(body):
            unit = (match.group("unit") or "").strip().casefold()
            column = (
                figures["percent"] if unit in {"%", "percent"}
                else figures["money"] if unit == "sgd"
                else figures["hours"] if unit
                else every
            )
            if _value(match.group("number")) not in column:
                errors.append(f"sow.md {heading}: figure {match.group(0).strip()!r} is not in the illustrative price table")
    for match in CURRENCY_FIGURE.finditer(sow_text):
        number = match.group("before") or match.group("after")
        if _value(number) not in figures["money"]:
            errors.append(f"sow.md: currency amount {match.group(0).strip()!r} is not in the illustrative price table")
    return errors


def check_sow(sow_path: Path, table_path: Path) -> dict:
    table_bytes = table_path.read_bytes()
    sow_bytes = sow_path.read_bytes()
    try:
        table = json.loads(table_bytes.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CheckError(f"price table is not JSON: {exc}") from exc
    errors = check_sow_figures(sow_bytes.decode("utf-8-sig"), table)
    return {
        "errors": errors,
        "price_table_sha256": sha256(table_bytes).hexdigest(),
        "sow_sha256": sha256(sow_bytes).hexdigest(),
        "sow_figures_checked": list(SOW_COMMERCIAL_SECTIONS) + ["currency amounts anywhere"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sow", type=Path, help="Factory v2: SOW whose figures must come from --price-table")
    parser.add_argument("--price-table", type=Path, help="Factory v2: the SI engine's illustrative price table")
    args = parser.parse_args()
    try:
        if (args.sow is None) != (args.price_table is None):
            raise CheckError("--sow and --price-table must be given together")
        report = check_csv(args.csv)
        if args.sow is not None:
            sow_report = check_sow(args.sow, args.price_table)
            report["errors"] = report["errors"] + sow_report.pop("errors")
            report.update(sow_report)
            report["passed"] = not report["errors"]
    except (OSError, CheckError) as exc:
        report = {"passed": False, "errors": [str(exc)]}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
