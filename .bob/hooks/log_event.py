"""PostToolUse and Stop hook: append a short, content-free record of each event to runs/hook-events.jsonl.

Each line holds the time, the event, the tool name, the run folder the tool touched (if any)
and the workspace-relative path. No file content, prompt text or MCP results are logged, and
a path outside the workspace is recorded only as "outside-workspace". The log is written only
when runs/ already exists inside the workspace. It never blocks Bob: any problem means the
event is skipped. No environment variables are needed.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePath


RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
PATH_KEYS = ("path", "file_path", "target", "filename", "directory")


def describe_path(raw: str, root: Path) -> tuple[str, str | None]:
    supplied = Path(raw)
    target = supplied if supplied.is_absolute() else root / supplied
    resolved = target.resolve()
    root_text = str(root).rstrip("\\/")
    if os.path.normcase(str(resolved)) == os.path.normcase(root_text):
        return ".", None
    if not os.path.normcase(str(resolved)).startswith(os.path.normcase(root_text) + os.sep):
        return "outside-workspace", None
    parts = PurePath(str(resolved)[len(root_text) + 1:]).parts
    run = parts[1] if len(parts) >= 2 and parts[0] == "runs" and RUN_NAME.fullmatch(parts[1]) else None
    return "/".join(parts)[:300], run


def main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if not isinstance(event, dict):
            return 0
        root = Path.cwd().resolve()
        runs = root / "runs"
        if runs.is_symlink() or not runs.is_dir():
            return 0
        log = runs / "hook-events.jsonl"
        if log.is_symlink():
            return 0
        tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
        raw = next((tool_input[key] for key in PATH_KEYS if isinstance(tool_input.get(key), str) and tool_input[key].strip()), None)
        path, run = describe_path(raw.strip(), root) if raw else (None, None)
        record = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": str(event.get("hook_event_name") or "")[:80],
            "tool": str(event.get("tool_name") or event.get("tool") or "")[:80],
            "run": run,
            "path": path,
        }
        with log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    except (OSError, ValueError, RuntimeError, UnicodeDecodeError):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
