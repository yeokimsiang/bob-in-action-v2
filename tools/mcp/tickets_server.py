"""Synthetic read-only tickets and incidents MCP server (stdio).

Serves the hash-pinned synthetic help-desk history in data/tickets.json. Records
are user reports, not diagnoses, and most are unrelated to code behaviour.
"""

from __future__ import annotations

from mcp_common import ToolError, load_pinned_dataset, parse_day, serve

SERVER = "tickets"
SEARCH_FIELDS = ("id", "title", "description", "reporter_role", "resolution_note")


def make_invoke(dataset: dict):
    records = dataset["records"]
    categories = dataset["categories"]

    def invoke(name: str, args: dict) -> object:
        if name == "tickets_search":
            query = args.get("q", "").strip().casefold()
            category = args.get("category", "")
            if category and category not in categories:
                raise ToolError("unknown category; known: " + ", ".join(sorted(categories)))
            selected = [r for r in records
                        if (not category or r["category"] == category)
                        and (not query or any(query in str(r[f]).casefold() for f in SEARCH_FIELDS))]
            return {"synthetic": True, "count": len(selected), "records": selected}
        if name == "tickets_get":
            for record in records:
                if record["id"] == args["id"]:
                    return record
            raise ToolError("unknown ticket id")
        if name == "incidents_list":
            since = parse_day(args["since"], "since").isoformat() if "since" in args else ""
            selected = [r for r in records if r["type"] == "incident" and r["reported_on"] >= since]
            return {"synthetic": True, "count": len(selected), "records": selected}
        raise KeyError(name)

    return invoke


def main() -> None:
    serve(SERVER, make_invoke(load_pinned_dataset("tickets")))


if __name__ == "__main__":
    main()
