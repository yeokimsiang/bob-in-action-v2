"""Synthetic read-only rate-card MCP server (stdio).

A view of the commercial engine's synthetic SGD rate card. It imports the pure
engine (validate, SEEDS) from tools/commercial/server.py read-only, starts no
HTTP server, opens no database and performs no pricing arithmetic: totals stay
with the commercial engine. The engine source is hash-pinned in datasets.json.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

from mcp_common import ROOT, ToolError, load_json, serve

SERVER = "ratecard"
REPO_ROOT = ROOT.parents[1]


def load_engine():
    entry = load_json(ROOT / "datasets.json")["datasets"]["ratecard_engine"]
    path = REPO_ROOT / entry["path"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != entry["sha256"]:
        raise RuntimeError(f"commercial engine hash mismatch: pinned {entry['sha256']}, actual {actual}")
    commercial_dir = str(path.parent)
    if commercial_dir not in sys.path:
        sys.path.insert(0, commercial_dir)  # server.py imports its sibling export_xlsx.
    spec = importlib.util.spec_from_file_location("commercial_engine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, entry


def build_view(engine, entry: dict) -> dict:
    cards, rates, assumptions = [], [], []
    for kind, ident, source in engine.SEEDS:
        validated = engine.validate(kind, source)  # The engine's own validation, unchanged.
        record = {"id": ident, **validated}
        if kind == "rate_card":
            cards.append(record)
        elif kind == "rate":
            rates.append(record)
        elif kind == "assumption":
            assumptions.append(record)
    if len(cards) != 1:
        raise RuntimeError("expected exactly one synthetic rate card in SEEDS")
    return {
        "synthetic": True,
        "approved": False,
        "notice": "Synthetic, unapproved demonstration rate card. Not a commercial offer. The commercial engine performs all arithmetic; this view returns no totals.",
        "card": cards[0],
        "rates": [r for r in rates if r["card_id"] == cards[0]["id"]],
        "assumptions": assumptions,
        "source": {"path": entry["path"], "sha256": entry["sha256"], "symbols": ["validate", "SEEDS"]},
    }


def make_invoke(view: dict):
    def invoke(name: str, args: dict) -> object:
        if name == "ratecard_get":
            role = args.get("role", "")
            if not role:
                return view
            rates = [r for r in view["rates"] if r["role"] == role]
            if not rates:
                raise ToolError("role not on the synthetic rate card; known: " + ", ".join(r["role"] for r in view["rates"]))
            return {**view, "rates": rates}
        if name == "ratecard_roles":
            return {"synthetic": True, "card_id": view["card"]["id"], "currency": view["card"]["currency"],
                    "roles": [r["role"] for r in view["rates"]]}
        raise KeyError(name)

    return invoke


def main() -> None:
    engine, entry = load_engine()
    serve(SERVER, make_invoke(build_view(engine, entry)))


if __name__ == "__main__":
    main()
