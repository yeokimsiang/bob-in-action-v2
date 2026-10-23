"""Price Bob's effort rows with the SI commercial engine (illustrative, not a quote).

Run this after /price and after validate_effort.py has rendered effort-model.csv. It
calls the engine's pure functions (tools/commercial/server.py): synthetic seeds, no
server and no database. Bob does no price arithmetic; this tool does it all. The table
is not a report and carries no approval. check_effort_numbers.py then cross-checks
every figure in Bob's sow.md against it.

    python tools/checkers/illustrative_price.py --csv runs/<name>/reports/effort-model.csv --output runs/<name>/checks/illustrative-price.json

sow.md beside the CSV supplies Bob's "## Risk drivers" table; the synthetic pilot
timesheets come from tools/mcp/data/timesheets.json. A missing input makes only its
pricing view not-available, never invented.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType
from typing import Any


class IllustrativePriceError(ValueError):
    """The engine could not produce an honest illustrative table; the price gate fails closed."""


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_RELATIVE = Path("tools/commercial/server.py")
VIEWS_RELATIVE = Path("tools/commercial/pricing_views.py")
VIEWS_CONFIG_RELATIVE = Path("tools/commercial/pricing-views.json")
TIMESHEETS_RELATIVE = Path("tools/mcp/data/timesheets.json")
ROLE_MAP_RELATIVE = Path("tools/commercial/commercial-illustration.json")
NO_RATE_CARD_ROLE = "(no rate-card role)"
SUMMARY_PREFIXES = ("GRAND TOTAL ALL INCLUDED", "EXCLUDED TOTAL ", "FUTURE FORECAST TOTAL", "ASSESSMENT+PILOT TOTAL")


def _source(repo_root: Path, relative: Path) -> dict[str, str]:
    path = repo_root / relative
    if path.is_symlink() or not path.is_file():
        raise IllustrativePriceError(f"Illustrative pricing input is missing or unsafe: {relative.as_posix()}")
    return {"path": relative.as_posix(), "sha256": sha256(path.read_bytes()).hexdigest()}


def load_commercial_engine(repo_root: Path) -> ModuleType:
    """Import the engine module for its pure functions; never start its HTTP server."""
    commercial = repo_root / ENGINE_RELATIVE.parent
    if str(commercial) not in sys.path:
        sys.path.insert(0, str(commercial))
    spec = importlib.util.spec_from_file_location("si_commercial_engine", commercial / ENGINE_RELATIVE.name)
    if spec is None or spec.loader is None:
        raise IllustrativePriceError("The SI commercial engine is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pricing_views(repo_root: Path) -> ModuleType:
    """Import the engine's pure pricing-views module under a private name."""
    spec = importlib.util.spec_from_file_location("si_pricing_views", repo_root / VIEWS_RELATIVE)
    if spec is None or spec.loader is None:
        raise IllustrativePriceError("The SI pricing views are unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.name


def _risk_drivers(views: ModuleType, sow_path: Path | None, wbs_ids: set[str]) -> tuple[Any, dict[str, str] | None]:
    """Bob's risk drivers, or the reason they are not available; fails closed on a malformed table."""
    if sow_path is None:
        return "no sow.md was supplied, so there is no '## Risk drivers' table", None
    if sow_path.is_symlink() or not sow_path.is_file():
        return f"{sow_path.name} is absent, so there is no '## Risk drivers' table", None
    try:
        drivers = views.parse_risk_drivers(sow_path.read_bytes().decode("utf-8-sig"), wbs_ids)
    except (views.PricingViewError, UnicodeError) as exc:
        raise IllustrativePriceError(f"Illustrative pricing refused the sow.md risk drivers: {exc}") from exc
    if drivers is None:
        return f"{sow_path.name} has no '## Risk drivers' section", None
    canonical = json.dumps(drivers, sort_keys=True, default=str, separators=(",", ":"), ensure_ascii=False)
    return drivers, {"path": f"{sow_path.name}#risk-drivers", "sha256": sha256(canonical.encode("utf-8")).hexdigest()}


def _pilot(views: ModuleType, root: Path, path: Path | None, rate_roles: set[str]) -> tuple[Any, dict[str, str] | None]:
    """The pilot timesheet summary, or the reason it is not available; fails closed on a bad file."""
    if path is None:
        return "no pilot timesheets were supplied", None
    shown = _display_path(root, path)
    if path.is_symlink() or not path.is_file():
        return f"{shown} is absent", None
    data = path.read_bytes()
    try:
        summary = views.parse_timesheets(json.loads(data.decode("utf-8-sig")), rate_roles)
    except (views.PricingViewError, UnicodeError, json.JSONDecodeError) as exc:
        raise IllustrativePriceError(f"Illustrative pricing refused the pilot timesheets: {exc}") from exc
    return summary, {"path": shown, "sha256": sha256(data).hexdigest()}


def _effort_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        row for row in rows
        if (row.get("wbs_id") or "").strip() and not (row.get("task_name") or "").startswith(SUMMARY_PREFIXES)
    ]


def build_illustrative_price(
    repo_root: Path,
    csv_path: Path,
    *,
    run_id: str,
    sow_path: Path | None = None,
    timesheets_path: Path | None = None,
) -> dict[str, Any]:
    """Return the illustrative table for one run's effort-model.csv; refuse anything unpriceable.

    With Bob's sow.md (its ``## Risk drivers`` table) and the synthetic pilot timesheets, the table also
    carries the SI pricing views; a missing input makes only its views not-available, never invented.
    """
    root = repo_root.resolve()
    config = json.loads((root / ROLE_MAP_RELATIVE).read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != 1 or not isinstance(config.get("role_map"), dict):
        raise IllustrativePriceError("Unsupported commercial illustration role map")
    engine = load_commercial_engine(root)
    as_of = date.fromisoformat(str(config["as_of"]))
    effort_source = {"path": "effort-model.csv", "sha256": sha256(csv_path.read_bytes()).hexdigest()}
    rate_roles = {data["role"] for kind, _, data in engine.SEEDS if kind == "rate"}

    records: list[dict[str, Any]] = []

    def add(kind: str, record_id: str, data: dict[str, Any]) -> None:
        try:
            validated = engine.validate(kind, data)
        except ValueError as exc:
            raise IllustrativePriceError(f"Illustrative pricing refused {kind} {record_id}: {exc}") from exc
        records.append({"kind": kind, "id": record_id, "data": validated, "revision": 1, "updated_at": as_of.isoformat()})

    for kind, record_id, data in engine.SEEDS:
        if kind in ("rate_card", "rate", "assumption", "document"):
            add(kind, record_id, data)
    add("document", "BOB-EFFORT-MODEL", {
        "title": "Bob effort model", "version": "1", "source": effort_source["path"],
        "sha256": effort_source["sha256"], "status": "reference",
    })
    mapping: dict[str, dict[str, str]] = {}
    unpriced: list[dict[str, str]] = []
    excluded: list[str] = []
    effort_rows = _effort_rows(csv_path)
    for row in effort_rows:
        role = row["role"].strip()
        if row.get("included") != "included":
            excluded.append(row["wbs_id"])
            continue
        if role.endswith(NO_RATE_CARD_ROLE):
            unpriced.append({"wbs_id": row["wbs_id"], "role": role, "reason": "no rate-card role"})
            continue
        if role in rate_roles:
            rate_role, basis = role, "rate-card role"
        elif role in config["role_map"]:
            rate_role, basis = str(config["role_map"][role]), "commercial-illustration role_map"
        else:
            raise IllustrativePriceError(f"Illustrative pricing has no rate-card role for effort role {role!r}")
        mapping.setdefault(role, {"effort_role": role, "rate_card_role": rate_role, "basis": basis})
        add("work_package", row["wbs_id"], {
            "name": row["task_name"][:140], "role": rate_role, "low_hours": row["low_hours"],
            "central_hours": row["central_hours"], "high_hours": row["high_hours"],
            "inclusion": row["task_name"][:1000], "evidence_ids": ["BOB-EFFORT-MODEL"],
        })
    if not mapping:
        raise IllustrativePriceError("Illustrative pricing found no included effort row with a rate-card role")
    result = engine.build_bob_input(records, as_of=as_of, illustrative=True)
    if (
        result.get("pricing_status") != "illustrative"
        or result.get("commercial_authorization", {}).get("client_quote_allowed") is not False
    ):
        raise IllustrativePriceError(
            f"The SI engine did not calculate an illustrative table: {result.get('calculation_blockers')}"
        )
    views_module = load_pricing_views(root)
    inputs: dict[str, dict[str, str]] = {
        "effort_model": effort_source,
        "engine": _source(root, ENGINE_RELATIVE),
        "role_map": _source(root, ROLE_MAP_RELATIVE),
        "pricing_views": _source(root, VIEWS_RELATIVE),
        "pricing_views_config": _source(root, VIEWS_CONFIG_RELATIVE),
    }
    drivers, drivers_source = _risk_drivers(views_module, sow_path, {row["wbs_id"] for row in effort_rows})
    pilot, pilot_source = _pilot(views_module, root, timesheets_path, rate_roles)
    for name, source in (("risk_drivers", drivers_source), ("timesheets", pilot_source)):
        if source is not None:
            inputs[name] = source
    rates = {data["role"]: Decimal(data["hourly_rate"]) for kind, _, data in engine.SEEDS if kind == "rate"}
    try:
        views_config = views_module.load_config(
            json.loads((root / VIEWS_CONFIG_RELATIVE).read_text(encoding="utf-8-sig"))
        )
        views = views_module.build_views(result, config=views_config, rates=rates, risk_drivers=drivers, pilot=pilot)
    except views_module.PricingViewError as exc:
        raise IllustrativePriceError(f"Illustrative pricing views refused: {exc}") from exc
    index = views["checker_index"]
    clash = (set(index["totals"]) & set(result["totals"])) | (set(index["effort_totals_hours"]) & set(result["effort_totals_hours"]))
    if clash:
        raise IllustrativePriceError(f"Pricing-view index would overwrite engine figures: {sorted(clash)}")
    result["totals"].update(index["totals"])
    result["effort_totals_hours"].update(index["effort_totals_hours"])
    return {
        "schema_version": 1,
        "kind": "si-illustrative-price-table",
        "run_id": run_id,
        "label": str(config.get("label") or "Synthetic illustration — not a quote."),
        "pricing_status": "illustrative",
        "not_a_quote": True,
        "synthetic_demo": True,
        "authored_by_bob": False,
        "produced_by": "tools/checkers/illustrative_price.py calling the SI commercial engine's pure functions",
        "report": False,
        "as_of": as_of.isoformat(),
        "inputs": inputs,
        "role_mapping": list(mapping.values()),
        "unpriced_rows": unpriced,
        "excluded_rows": excluded,
        "engine_result": result,
        "pricing_views": views,
    }


def _default_run_id(csv_path: Path) -> str:
    """runs/<name>/reports/effort-model.csv gives <name>; any other CSV its folder name."""
    folder = csv_path.parent
    return folder.parent.name if folder.name == "reports" else folder.name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Price a validated effort-model.csv with the SI engine (illustrative, not a quote).")
    parser.add_argument("--csv", required=True, type=Path, help="effort-model.csv rendered by validate_effort.py")
    parser.add_argument("--output", required=True, type=Path, help="new JSON file to write; an existing file is refused")
    parser.add_argument("--sow", type=Path, help="Bob's sow.md (default: sow.md beside the CSV)")
    parser.add_argument("--timesheets", type=Path, help="synthetic pilot timesheets (default: tools/mcp/data/timesheets.json)")
    parser.add_argument("--run-id", help="label for the table (default: the run folder name)")
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        print(f"illustrative_price.py: {args.output} already exists; choose a new path", file=sys.stderr)
        return 2
    try:
        table = build_illustrative_price(
            REPO_ROOT, args.csv.resolve(), run_id=args.run_id or _default_run_id(args.csv.resolve()),
            sow_path=args.sow or args.csv.with_name("sow.md"),
            timesheets_path=args.timesheets or REPO_ROOT / TIMESHEETS_RELATIVE,
        )
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"passed": False, "errors": [str(exc)]}, indent=2))
        return 1
    data = (json.dumps(table, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(data)
    totals = table["engine_result"]["totals"]
    print(json.dumps({"passed": True, "output": str(args.output), "sha256": sha256(data).hexdigest(),
                      "pricing_status": table["pricing_status"], "not_a_quote": table["not_a_quote"],
                      "bands": sorted(totals)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
