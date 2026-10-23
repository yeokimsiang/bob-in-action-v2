"""SI engine pricing views beside the flat allowance (synthetic SGD, illustrative, not a quote).

Bob makes the judgements: named risk drivers with a likelihood and an hours impact, written in
sow.md under ``## Risk drivers``. This module does all the arithmetic, with Decimal and the
engine's money convention (cents, ROUND_HALF_UP). It is pure: callers read files and pass data in.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any, Iterable


# The engine's money convention (server.MONEY and server.money): cents, ROUND_HALF_UP. Kept local so
# this module never imports a module named "server" (another SI tool has one too); a test pins equality.
MONEY = Decimal("0.01")


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


class PricingViewError(ValueError):
    """An input cannot be priced honestly; the caller fails closed."""


CONFIG_NAME = "pricing-views.json"
CONFIG_KIND = "si-pricing-views-config"
RULE_NAMES = ("flat_contingency", "risk_based_contingency", "calibration", "fixed_price",
              "capped_time_and_materials", "pilot_then_programme")
FRACTION_TEXT = re.compile(r"(?:0|1)(?:\.\d{1,4})?")


def _fraction(value: Any, name: str) -> Decimal:
    if not isinstance(value, str) or not FRACTION_TEXT.fullmatch(value) or Decimal(value) > 1:
        raise PricingViewError(f"pricing-views config {name} must be a decimal string between 0 and 1")
    return Decimal(value)


def load_config(data: Any) -> dict[str, Any]:
    """Validate the small synthetic assumptions file (likelihood weights, narrowing fraction, rules)."""
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("kind") != CONFIG_KIND:
        raise PricingViewError(f"pricing-views config must be {CONFIG_KIND} schema_version 1")
    if data.get("synthetic") is not True:
        raise PricingViewError("pricing-views config must be marked synthetic: true")
    label = data.get("label")
    if not isinstance(label, str) or "not a quote" not in label:
        raise PricingViewError("pricing-views config label must say 'not a quote'")
    weights = data.get("likelihood_weights")
    if not isinstance(weights, dict) or set(weights) != set(LIKELIHOODS):
        raise PricingViewError(f"pricing-views config likelihood_weights must name exactly {', '.join(LIKELIHOODS)}")
    rules = data.get("rules")
    if not isinstance(rules, dict) or any(not isinstance(rules.get(name), str) or not rules[name].strip() for name in RULE_NAMES):
        raise PricingViewError(f"pricing-views config rules must document {', '.join(RULE_NAMES)}")
    return {
        "label": label,
        "likelihood_weights": {name: _fraction(weights[name], f"likelihood_weights.{name}") for name in LIKELIHOODS},
        "range_narrowing_fraction": _fraction(data.get("range_narrowing_fraction"), "range_narrowing_fraction"),
        "rules": {name: rules[name].strip() for name in RULE_NAMES},
    }


RISK_HEADING = "## Risk drivers"
RISK_HEADER = ("ID", "Risk driver", "Likelihood", "Hours impact", "Affects")
LIKELIHOODS = ("Low", "Medium", "High")
DRIVER_ID = re.compile(r"RD-\d{2,}")
WHOLE_HOURS = re.compile(r"[1-9]\d*")
SEPARATOR_CELL = re.compile(r":?-{3,}:?")
NEXT_HEADING = re.compile(r"#{1,2}\s")


def _cells(line: str) -> list[str] | None:
    text = line.strip()
    if len(text) < 2 or not (text.startswith("|") and text.endswith("|")):
        return None
    return [cell.strip() for cell in text[1:-1].split("|")]


def parse_risk_drivers(sow_text: str, wbs_ids: Iterable[str]) -> list[dict[str, Any]] | None:
    """Return Bob's risk drivers from sow.md, or None when the section is absent.

    The section's heading line is exactly ``## Risk drivers``; its first content is a markdown
    table with exactly the RISK_HEADER columns. Any malformed row fails the whole table.
    """
    known = set(wbs_ids)
    lines = sow_text.splitlines()
    starts = [index for index, line in enumerate(lines) if line.rstrip() == RISK_HEADING]
    if not starts:
        return None
    if len(starts) > 1:
        raise PricingViewError("sow.md has more than one '## Risk drivers' section")
    body: list[str] = []
    for line in lines[starts[0] + 1:]:
        if NEXT_HEADING.match(line):
            break
        body.append(line)
    content = [line for line in body if line.strip()]
    header = "| " + " | ".join(RISK_HEADER) + " |"
    if not content or _cells(content[0]) != list(RISK_HEADER):
        raise PricingViewError(f"'## Risk drivers' must start with the table header {header}")
    separator = _cells(content[1]) if len(content) > 1 else None
    if separator is None or len(separator) != len(RISK_HEADER) or not all(SEPARATOR_CELL.fullmatch(c) for c in separator):
        raise PricingViewError("'## Risk drivers' table header must be followed by a five-column separator row")
    start = body.index(content[1]) + 1
    rows: list[str] = []
    for line in body[start:]:
        if not line.strip().startswith("|"):
            break
        rows.append(line)
    if not rows:
        raise PricingViewError("'## Risk drivers' table has no risk-driver rows")
    drivers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in rows:
        cells = _cells(line)
        if cells is None or len(cells) != len(RISK_HEADER):
            raise PricingViewError(f"risk-driver row must have exactly five cells: {line.strip()!r}")
        identifier, driver, likelihood, hours, affects = cells
        if not DRIVER_ID.fullmatch(identifier):
            raise PricingViewError(f"risk-driver ID must look like RD-01: {identifier!r}")
        if identifier in seen:
            raise PricingViewError(f"duplicate risk-driver ID {identifier}")
        seen.add(identifier)
        if not driver:
            raise PricingViewError(f"{identifier}: risk driver text is empty")
        if likelihood not in LIKELIHOODS:
            raise PricingViewError(f"{identifier}: likelihood must be one of {', '.join(LIKELIHOODS)}, not {likelihood!r}")
        if not WHOLE_HOURS.fullmatch(hours):
            raise PricingViewError(f"{identifier}: hours impact must be a positive whole number of hours, not {hours!r}")
        affected = [item.strip() for item in affects.split(",")]
        for wbs_id in affected:
            if wbs_id not in known:
                raise PricingViewError(f"{identifier}: unknown WBS id {wbs_id!r} (not in the effort model)")
        if len(set(affected)) != len(affected):
            raise PricingViewError(f"{identifier}: a WBS id is listed twice in Affects")
        drivers.append({
            "id": identifier, "driver": driver, "likelihood": likelihood, "hours_impact": Decimal(hours),
            "affects": affected,
        })
    return drivers


TIMESHEET_SCHEMA = "si-mock-timesheets/v1"


HOURS_TEXT = re.compile(r"\d{1,6}(?:\.\d{1,2})?")


def _text(record: Any, key: str, where: str) -> str:
    value = record.get(key) if isinstance(record, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise PricingViewError(f"timesheets {where}: {key} must be nonempty text")
    return value.strip()


def _hours(record: dict, key: str, where: str, *, upper: Decimal) -> Decimal:
    value = record.get(key)
    if not isinstance(value, str) or not HOURS_TEXT.fullmatch(value) or not Decimal(0) < Decimal(value) <= upper:
        raise PricingViewError(f"timesheets {where}: {key} must be a positive decimal string of hours, not {value!r}")
    return Decimal(value)


def parse_timesheets(data: Any, rate_roles: Iterable[str]) -> dict[str, Any]:
    """Summarise the synthetic pilot timesheets: planned and actual hours, actual hours by role.

    Every entry must name a rate-card role and a planned pilot work package; anything else fails closed.
    """
    roles = set(rate_roles)
    if not isinstance(data, dict):
        raise PricingViewError("timesheets must be a JSON object")
    if data.get("schema") != TIMESHEET_SCHEMA:
        raise PricingViewError(f"timesheets schema must be {TIMESHEET_SCHEMA}")
    if data.get("synthetic") is not True:
        raise PricingViewError("timesheets must be marked synthetic: true")
    _text(data, "label", "file")
    pilot = data.get("pilot")
    name = _text(pilot, "name", "pilot")
    planned_items = pilot.get("planned")
    if not isinstance(planned_items, list) or not planned_items:
        raise PricingViewError("timesheets pilot.planned must list at least one work package")
    planned: dict[str, Decimal] = {}
    for item in planned_items:
        package = _text(item, "work_package", "pilot.planned")
        _text(item, "description", f"pilot.planned {package}")
        if package in planned:
            raise PricingViewError(f"timesheets pilot.planned has a duplicate work package {package}")
        planned[package] = _hours(item, "planned_hours", f"pilot.planned {package}", upper=Decimal(100000))
    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise PricingViewError("timesheets entries must list at least one entry")
    by_role: dict[str, Decimal] = {}
    seen: set[str] = set()
    for entry in entries:
        entry_id = _text(entry, "entry_id", "entry")
        if entry_id in seen:
            raise PricingViewError(f"timesheets has a duplicate entry {entry_id}")
        seen.add(entry_id)
        _text(entry, "person", entry_id)
        _text(entry, "activity", entry_id)
        role = _text(entry, "role", entry_id)
        if role not in roles:
            raise PricingViewError(f"timesheets {entry_id}: role {role!r} is not a rate-card role")
        package = _text(entry, "work_package", entry_id)
        if package not in planned:
            raise PricingViewError(f"timesheets {entry_id}: unplanned work package {package!r}")
        when = _text(entry, "date", entry_id)
        try:
            if date.fromisoformat(when).isoformat() != when:
                raise ValueError(when)
        except ValueError as exc:
            raise PricingViewError(f"timesheets {entry_id}: date must be YYYY-MM-DD, not {when!r}") from exc
        hours = _hours(entry, "hours", entry_id, upper=Decimal(24))
        by_role[role] = by_role.get(role, Decimal(0)) + hours
    return {
        "name": name, "planned_hours": sum(planned.values(), Decimal(0)),
        "actual_hours": sum(by_role.values(), Decimal(0)),
        "actual_hours_by_role": dict(sorted(by_role.items())), "entry_count": len(entries),
    }


BANDS = ("low", "central", "high")
HOURS = Decimal("0.01")
PERCENT = Decimal("0.01")
FACTOR = Decimal("0.0001")


def _hours_text(value: Decimal) -> str:
    return str(value.quantize(HOURS, rounding=ROUND_HALF_UP))


def _percent(part: Decimal, whole: Decimal) -> str:
    return str((part * 100 / whole).quantize(PERCENT, rounding=ROUND_HALF_UP)) if whole else "0.00"


def _not_available(reason: str) -> dict[str, str]:
    return {"status": "not-available", "reason": reason}


def _flat(engine: dict, rule: str) -> dict[str, Any]:
    totals = engine["totals"]
    return {
        "status": "available", "rule": rule, "percent": totals["central"]["risk_allowance_percent"],
        "bands": {band: {"subtotal_sgd": totals[band]["subtotal_sgd"], "contingency_sgd": totals[band]["risk_allowance_sgd"],
                         "total_sgd": totals[band]["total_excluding_tax_sgd"]} for band in BANDS},
    }


def _risk_based(engine: dict, drivers: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    packages = {line["package_id"]: line for line in engine["work_packages"]}
    central = Decimal(engine["totals"]["central"]["subtotal_sgd"])
    priced: list[dict[str, Any]] = []
    for driver in drivers:
        affected = [packages[wbs] for wbs in driver["affects"] if wbs in packages]
        if not affected:
            raise PricingViewError(f"{driver['id']}: affects no row the engine priced (included, with a rate-card role)")
        top = max(affected, key=lambda line: (Decimal(line["rate_sgd_per_hour"]), line["role"]))
        rate = Decimal(top["rate_sgd_per_hour"])
        weight = config["likelihood_weights"][driver["likelihood"]]
        weighted = (weight * driver["hours_impact"]).quantize(HOURS, rounding=ROUND_HALF_UP)
        contingency = (weighted * rate).quantize(MONEY, rounding=ROUND_HALF_UP)
        exposed = sum((Decimal(line["subtotals_sgd"]["central"]) for line in affected), Decimal(0))
        priced.append({
            "id": driver["id"], "driver": driver["driver"], "likelihood": driver["likelihood"],
            "likelihood_weight": str(weight), "hours_impact": str(driver["hours_impact"]),
            "weighted_hours": str(weighted), "affects": list(driver["affects"]),
            "priced_affects": [line["package_id"] for line in affected],
            "unpriced_affects": [wbs for wbs in driver["affects"] if wbs not in packages],
            "rate_role": top["role"], "rate_sgd_per_hour": money(rate),
            "affected_central_subtotal_sgd": money(exposed), "contingency_sgd": money(contingency),
            "percent_of_affected_central": _percent(contingency, exposed),
            "affected_central_total_sgd": money(exposed + contingency),
        })
    total = sum((Decimal(item["contingency_sgd"]) for item in priced), Decimal(0))
    return {
        "status": "available", "rule": config["rules"]["risk_based_contingency"],
        "likelihood_weights": {name: str(value) for name, value in config["likelihood_weights"].items()},
        "drivers": priced,
        "weighted_hours": _hours_text(sum((Decimal(item["weighted_hours"]) for item in priced), Decimal(0))),
        "contingency_sgd": money(total), "central_subtotal_sgd": money(central),
        "percent_of_central_subtotal": _percent(total, central), "central_total_sgd": money(central + total),
    }


def _pilot_summary(pilot: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": pilot["name"], "planned_hours": str(pilot["planned_hours"]), "actual_hours": str(pilot["actual_hours"]),
        "actual_hours_by_role": {role: str(hours) for role, hours in pilot["actual_hours_by_role"].items()},
        "entry_count": pilot["entry_count"],
    }


def _calibration(engine: dict, pilot: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    factor = (pilot["actual_hours"] / pilot["planned_hours"]).quantize(FACTOR, rounding=ROUND_HALF_UP)
    narrowing = config["range_narrowing_fraction"]
    rows: list[dict[str, Any]] = []
    hours_total = dict.fromkeys(BANDS, Decimal(0))
    money_total = dict.fromkeys(BANDS, Decimal(0))
    within = True
    for line in engine["work_packages"]:
        low, central, high = (Decimal(line["hours"][band]) for band in BANDS)
        rate = Decimal(line["rate_sgd_per_hour"])
        mid = min(max((central * factor).quantize(HOURS, rounding=ROUND_HALF_UP), low), high).quantize(HOURS)
        calibrated = {
            "low": (mid - (mid - low) * narrowing).quantize(HOURS, rounding=ROUND_HALF_UP),
            "central": mid,
            "high": (mid + (high - mid) * narrowing).quantize(HOURS, rounding=ROUND_HALF_UP),
        }
        within = within and low <= calibrated["low"] <= mid <= calibrated["high"] <= high
        amounts = {band: (calibrated[band] * rate).quantize(MONEY, rounding=ROUND_HALF_UP) for band in BANDS}
        for band in BANDS:
            hours_total[band] += calibrated[band]
            money_total[band] += amounts[band]
        rows.append({
            "wbs_id": line["package_id"], "role": line["role"], "rate_sgd_per_hour": line["rate_sgd_per_hour"],
            "original_hours": dict(line["hours"]),
            "calibrated_hours": {band: str(calibrated[band]) for band in BANDS},
            "calibrated_subtotals_sgd": {band: money(amounts[band]) for band in BANDS},
        })
    if not within:
        raise PricingViewError("calibration left a row's original low-high range")
    percent = Decimal(engine["totals"]["central"]["risk_allowance_percent"])
    allowance = {band: (money_total[band] * percent / 100).quantize(MONEY, rounding=ROUND_HALF_UP) for band in BANDS}
    return {
        "status": "available", "rule": config["rules"]["calibration"], "pilot": _pilot_summary(pilot),
        "factor": str(factor), "range_narrowing_fraction": str(narrowing), "rows": rows,
        "original": {"hours": dict(engine["effort_totals_hours"]),
                     "subtotals_sgd": {band: engine["totals"][band]["subtotal_sgd"] for band in BANDS}},
        "calibrated": {"hours": {band: str(hours_total[band]) for band in BANDS},
                       "subtotals_sgd": {band: money(money_total[band]) for band in BANDS},
                       "flat_contingency_percent": str(percent),
                       "flat_contingency_sgd": {band: money(allowance[band]) for band in BANDS},
                       "flat_contingency_totals_sgd": {band: money(money_total[band] + allowance[band]) for band in BANDS}},
        "within_original_range": within,
    }


def _shapes(
    engine: dict, risk: dict[str, Any], calibration: dict[str, Any], pilot: dict[str, Any] | str,
    rates: dict[str, Decimal], config: dict[str, Any],
) -> dict[str, Any]:
    rules = config["rules"]
    percent = Decimal(engine["totals"]["central"]["risk_allowance_percent"])
    if calibration["status"] == "available":
        effort_basis, cap_basis = "calibrated central", "calibrated narrowed-high subtotal"
        hours, subtotals = calibration["calibrated"]["hours"], calibration["calibrated"]["subtotals_sgd"]
    else:
        effort_basis, cap_basis = "central", "high subtotal"
        hours = engine["effort_totals_hours"]
        subtotals = {band: engine["totals"][band]["subtotal_sgd"] for band in BANDS}
    base = Decimal(subtotals["central"])
    if risk["status"] == "available":
        contingency_basis, contingency = "risk-based", Decimal(risk["contingency_sgd"])
    else:
        contingency_basis = f"flat {percent}%"
        contingency = (base * percent / 100).quantize(MONEY, rounding=ROUND_HALF_UP)
    fixed = base + contingency
    cap = Decimal(subtotals["high"])
    shapes: dict[str, Any] = {
        "fixed_price": {
            "status": "available", "rule": rules["fixed_price"], "effort_basis": effort_basis,
            "contingency_basis": contingency_basis, "subtotal_sgd": money(base), "contingency_sgd": money(contingency),
            "contingency_percent_of_subtotal": _percent(contingency, base), "price_sgd": money(fixed),
        },
        "capped_time_and_materials": {
            "status": "available", "rule": rules["capped_time_and_materials"],
            "billing": "rate-card rates x hours worked, invoiced up to the cap", "effort_basis": effort_basis,
            "estimate_hours": hours["central"], "estimate_sgd": money(base), "cap_hours": hours["high"],
            "cap_sgd": money(cap), "cap_basis": cap_basis, "headroom_sgd": money(cap - base),
            "headroom_percent_of_estimate": _percent(cap - base, base),
        },
    }
    if isinstance(pilot, str):
        shapes["pilot_then_programme"] = _not_available(pilot)
        return shapes
    costs = {
        role: (hours_worked * rates[role]).quantize(MONEY, rounding=ROUND_HALF_UP)
        for role, hours_worked in pilot["actual_hours_by_role"].items()
    }
    pilot_price = sum(costs.values(), Decimal(0))
    shapes["pilot_then_programme"] = {
        "status": "available", "rule": rules["pilot_then_programme"],
        "pilot_phase": {"name": pilot["name"], "basis": "synthetic timesheet actuals at rate-card rates",
                        "hours": str(pilot["actual_hours"]),
                        "hours_by_role": {role: str(value) for role, value in pilot["actual_hours_by_role"].items()},
                        "price_sgd": money(pilot_price)},
        "programme_phase": {"basis": "fixed price", "price_sgd": money(fixed)},
        "pilot_percent_of_programme": _percent(pilot_price, fixed),
        "total_sgd": money(pilot_price + fixed),
    }
    return shapes


INDEX_NOTE = (
    "Copies of this section's hours and SGD figures in the engine's band shape, merged into engine_result "
    "(totals and effort_totals_hours) so the unchanged check_effort_numbers.py can match SOW figures against "
    "them. Each band: total_excluding_tax_sgd = subtotal_sgd + risk_allowance_sgd and risk_allowance_percent = "
    "allowance / subtotal x 100. Band meanings: risk_driver_* = affected rows' central subtotal + that driver's "
    "contingency; capped_time_and_materials = estimate + headroom = cap; pilot_then_programme = programme + "
    "pilot = total. Per-row calibration detail and unitless ratios (likelihood weights, calibration factor) "
    "are recorded above but not indexed."
)


def _line(subtotal: str, percent: str, allowance: str, total: str) -> dict[str, str]:
    return {"subtotal_sgd": subtotal, "risk_allowance_percent": percent, "risk_allowance_sgd": allowance,
            "total_excluding_tax_sgd": total}


def _checker_index(risk: dict[str, Any], calibration: dict[str, Any], shapes: dict[str, Any]) -> dict[str, Any]:
    totals: dict[str, dict[str, str]] = {}
    hours: dict[str, str] = {}
    if risk["status"] == "available":
        totals["risk_based_central"] = _line(risk["central_subtotal_sgd"], risk["percent_of_central_subtotal"],
                                             risk["contingency_sgd"], risk["central_total_sgd"])
        hours["risk_weighted_hours"] = risk["weighted_hours"]
        for driver in risk["drivers"]:
            totals[f"risk_driver_{driver['id']}"] = _line(
                driver["affected_central_subtotal_sgd"], driver["percent_of_affected_central"],
                driver["contingency_sgd"], driver["affected_central_total_sgd"])
            hours[f"risk_driver_{driver['id']}_hours_impact"] = driver["hours_impact"]
            hours[f"risk_driver_{driver['id']}_weighted_hours"] = driver["weighted_hours"]
    if calibration["status"] == "available":
        calibrated = calibration["calibrated"]
        for band in BANDS:
            totals[f"calibrated_{band}"] = _line(
                calibrated["subtotals_sgd"][band], calibrated["flat_contingency_percent"],
                calibrated["flat_contingency_sgd"][band], calibrated["flat_contingency_totals_sgd"][band])
            hours[f"calibrated_{band}"] = calibrated["hours"][band]
        pilot = calibration["pilot"]
        hours["pilot_planned"] = pilot["planned_hours"]
        hours["pilot_actual"] = pilot["actual_hours"]
        for role, value in pilot["actual_hours_by_role"].items():
            hours[f"pilot_actual_{role}"] = value
    fixed = shapes["fixed_price"]
    totals["fixed_price"] = _line(fixed["subtotal_sgd"], fixed["contingency_percent_of_subtotal"],
                                  fixed["contingency_sgd"], fixed["price_sgd"])
    capped = shapes["capped_time_and_materials"]
    totals["capped_time_and_materials"] = _line(capped["estimate_sgd"], capped["headroom_percent_of_estimate"],
                                                capped["headroom_sgd"], capped["cap_sgd"])
    phased = shapes["pilot_then_programme"]
    if phased["status"] == "available":
        totals["pilot_then_programme"] = _line(phased["programme_phase"]["price_sgd"], phased["pilot_percent_of_programme"],
                                               phased["pilot_phase"]["price_sgd"], phased["total_sgd"])
    return {"note": INDEX_NOTE, "totals": totals, "effort_totals_hours": hours}


def build_views(
    engine: dict[str, Any],
    *,
    config: dict[str, Any],
    rates: dict[str, Decimal],
    risk_drivers: list[dict[str, Any]] | str,
    pilot: dict[str, Any] | str,
) -> dict[str, Any]:
    """Price the same effort several ways. A str for risk_drivers or pilot is its not-available reason."""
    if engine.get("pricing_status") != "illustrative" or not isinstance(engine.get("totals"), dict):
        raise PricingViewError("pricing views need the engine's calculated illustrative result")
    risk = (
        _not_available(risk_drivers) if isinstance(risk_drivers, str)
        else _risk_based(engine, risk_drivers, config)
    )
    calibration = _not_available(pilot) if isinstance(pilot, str) else _calibration(engine, pilot, config)
    shapes = _shapes(engine, risk, calibration, pilot, rates, config)
    return {
        "schema_version": 1, "label": config["label"], "pricing_status": "illustrative", "not_a_quote": True,
        "synthetic": True, "authored_by_bob": False,
        "flat_contingency": _flat(engine, config["rules"]["flat_contingency"]),
        "risk_based_contingency": risk,
        "calibration": calibration,
        "commercial_shapes": shapes,
        "checker_index": _checker_index(risk, calibration, shapes),
    }
