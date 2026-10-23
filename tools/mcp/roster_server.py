"""Synthetic read-only roster MCP server (stdio).

Serves the hash-pinned synthetic delivery roster in data/roster.json. The
people, skills and availability are invented demonstration data, not HR records.
"""

from __future__ import annotations

from mcp_common import ToolError, load_pinned_dataset, parse_day, serve

SERVER = "roster"


def make_invoke(dataset: dict):
    people = dataset["records"]

    def invoke(name: str, args: dict) -> object:
        if name == "roster_list_people":
            role = args.get("role", "")
            selected = [p for p in people if not role or p["role"] == role]
            return {"synthetic": True, "count": len(selected), "people": selected}
        if name == "roster_find_by_skill":
            skill = args["skill"].strip().casefold()
            if not skill:
                raise ToolError("skill must not be empty")
            selected = [p for p in people if any(s.casefold() == skill for s in p["skills"])]
            return {"synthetic": True, "skill": args["skill"], "count": len(selected), "people": selected}
        if name == "roster_availability":
            start, end = parse_day(args["from"], "from"), parse_day(args["to"], "to")
            if end < start:
                raise ToolError("to precedes from")
            result = []
            for person in people:
                windows = []
                for window in person["availability"]:
                    w_start, w_end = parse_day(window["from"], "from"), parse_day(window["to"], "to")
                    if w_start <= end and w_end >= start:
                        windows.append({"from": max(w_start, start).isoformat(), "to": min(w_end, end).isoformat(),
                                        "allocation_percent": window["allocation_percent"]})
                result.append({"id": person["id"], "name": person["name"], "role": person["role"],
                               "ratecard_role": person["ratecard_role"], "windows": windows})
            return {"synthetic": True, "from": args["from"], "to": args["to"], "people": result}
        raise KeyError(name)

    return invoke


def main() -> None:
    serve(SERVER, make_invoke(load_pinned_dataset("roster")))


if __name__ == "__main__":
    main()
