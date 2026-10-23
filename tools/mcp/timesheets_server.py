"""Synthetic read-only pilot timesheets MCP server (stdio).

Serves the hash-pinned synthetic timesheets in data/timesheets.json for the Java
invoice-preview pilot: planned hours per pilot work package and the booked time
entries. Hours are decimal strings; the summary sums them exactly with Decimal.
It computes no rates, prices or calibration factors: those stay with the SI engine.
"""

from __future__ import annotations

from decimal import Decimal

from mcp_common import ToolError, load_pinned_dataset, serve

SERVER = "timesheets"


def make_invoke(dataset: dict):
    label = dataset["label"]
    pilot = dataset["pilot"]
    planned = pilot["planned"]
    entries = dataset["entries"]
    packages = [item["work_package"] for item in planned]

    def invoke(name: str, args: dict) -> object:
        if name == "timesheets_list_entries":
            package = args.get("work_package", "")
            if package and package not in packages:
                raise ToolError("unknown work_package; known: " + ", ".join(packages))
            selected = [e for e in entries if not package or e["work_package"] == package]
            return {"synthetic": True, "label": label, "count": len(selected), "entries": selected}
        if name == "timesheets_pilot_summary":
            rows = []
            for item in planned:
                booked = [e for e in entries if e["work_package"] == item["work_package"]]
                rows.append({"work_package": item["work_package"], "description": item["description"],
                             "planned_hours": item["planned_hours"],
                             "actual_hours": str(sum((Decimal(e["hours"]) for e in booked), Decimal("0"))),
                             "entry_count": len(booked)})
            return {"synthetic": True, "label": label, "pilot": pilot["name"], "work_packages": rows,
                    "totals": {"planned_hours": str(sum((Decimal(i["planned_hours"]) for i in planned), Decimal("0"))),
                               "actual_hours": str(sum((Decimal(e["hours"]) for e in entries), Decimal("0"))),
                               "entry_count": len(entries)}}
        raise KeyError(name)

    return invoke


def main() -> None:
    serve(SERVER, make_invoke(load_pinned_dataset("timesheets")))


if __name__ == "__main__":
    main()
