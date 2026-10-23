"""SessionStart and UserPromptSubmit hook: confirm the SI kit is in place before Bob works.

Runs from the folder Bob has open. It checks that the kit files the guard and the commands
rely on exist and that no evaluator-only folder sits at the top of the workspace. At session
start it prints one status line that Bob sees as context; on a prompt it stays silent unless
something is wrong. Exit 2 on a prompt blocks that prompt. No environment variables, no
network, no Bob credits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


FORBIDDEN = ("IDEAL", "COMPARISON", "OTHERS", "answer-key", "blueprint")
REQUIRED = (
    ".bob/custom_modes.yaml",
    ".bob/settings.json",
    ".bob/mcp.json",
    ".bob/hooks/pre_tool_guard.py",
    "tools/mcp/launch.py",
    "app/pom.xml",
)
STATUS = "SI kit hooks active: the guard allows reads in this workspace and writes only under runs/<name>/."


def read_event() -> dict:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
        event = json.loads(raw) if raw.strip() else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        event = {}
    return event if isinstance(event, dict) else {}


def main() -> int:
    event = read_event()
    workspace = Path.cwd().resolve()
    errors = [f"evaluator-only folder present: {name}" for name in FORBIDDEN if (workspace / name).exists()]
    errors.extend(f"missing kit file: {name} (open the repository root in Bob)" for name in REQUIRED if not (workspace / name).is_file())
    prompt = str(event.get("hook_event_name") or "") == "UserPromptSubmit"
    if errors:
        print(json.dumps({"hook": "preflight", "ok": False, "errors": errors}, sort_keys=True))
        print("Blocked by the SI kit preflight: " + "; ".join(errors), file=sys.stderr)
        return 2
    if not prompt:
        print(STATUS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
