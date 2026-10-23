"""Start one synthetic read-only mock MCP server by name: launch.py <server>.

The repository .bob/mcp.json points every server entry at this file, so the
entries work from any clone and any working directory: the server script, the
contract and the pinned datasets are all found relative to this file. Only the
servers declared in contract.json can be started. The server runs in this
process, so its stdio is the MCP channel.
"""

from __future__ import annotations

from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent


def server_script(name: str) -> Path:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))  # The servers import their sibling mcp_common.
    from mcp_common import load_contract

    declared = load_contract()["servers"]
    if name not in declared:
        raise ValueError(f"unknown mock MCP server {name!r}; declared: {', '.join(sorted(declared))}")
    script = ROOT.parents[1] / declared[name]["entrypoint"]
    if script.resolve().parent != ROOT or not script.is_file():
        raise ValueError(f"mock MCP server {name!r} has no entrypoint beside the launcher")
    return script


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: launch.py <server>", file=sys.stderr)
        return 2
    try:
        script = server_script(argv[0])
    except ValueError as exc:
        print(f"launch.py: {exc}", file=sys.stderr)
        return 2
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
