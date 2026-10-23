"""PreToolUse guard for the SI kit: Bob may read the workspace and write only its own run folder.

Bob runs this before every tool call (wired in .bob/settings.json) with the call as JSON on
stdin, from the folder Bob has open (the workspace). Exit 0 allows the call; exit 2 blocks it
and the reason goes to stderr. It needs no environment variables.

Rules:
  a. Reads (read, list, glob, grep, search) only inside the workspace. Evaluator-only folders,
     internal working folders and secret-looking files are refused even there.
  b. Writes (write, edit, patch, diff, insert, replace, mkdir) only inside runs/<name>/, where
     <name> matches [A-Za-z0-9][A-Za-z0-9._-]*. Any ".." in the path, a symlink or junction that
     leads elsewhere, and everything outside runs/ (app/, tools/, targets/, .bob/) are refused.
  c. Shell commands and delete, move or rename calls are always refused.
  d. MCP calls only for the ten read-only tools of the roster, ratecard, tickets and
     timesheets servers in tools/mcp/, and the read-only run_stage_checks tool of the checks
     server in tools/checkers/. MCP resource reads are refused.
  e. Any other tool that names a path gets the read check; one that names none is allowed.

This is a backstop for honest mistakes, not a security sandbox: it sees only what Bob's tool
call declares.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path, PurePath


RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
ALLOWED_MCP_TOOLS = frozenset({
    "mcp__roster__roster_list_people",
    "mcp__roster__roster_find_by_skill",
    "mcp__roster__roster_availability",
    "mcp__ratecard__ratecard_get",
    "mcp__ratecard__ratecard_roles",
    "mcp__tickets__tickets_search",
    "mcp__tickets__tickets_get",
    "mcp__tickets__incidents_list",
    "mcp__timesheets__timesheets_list_entries",
    "mcp__timesheets__timesheets_pilot_summary",
    "mcp__checks__run_stage_checks",
})
MCP_TOOL = re.compile(r"^mcp__([A-Za-z0-9_-]+?)__([A-Za-z0-9_-]+)$")

EXEC_TOOLS = re.compile(r"(execute_command|run_command|shell|terminal|bash|powershell|cmd_exec|exec)", re.IGNORECASE)
DESTRUCTIVE_TOOLS = re.compile(r"(delete|remove|move|rename|unlink|rmdir)", re.IGNORECASE)
WRITE_TOOLS = re.compile(r"(write|edit|patch|diff|replace|insert|append|mkdir|create_dir|create_file|str_replace)", re.IGNORECASE)
# Read tools that search the workspace root when no path is given.
ROOTED_READ_TOOLS = frozenset({"grep", "glob", "search_files", "list_files", "list_directory", "codebase_search"})
# Read tools that must name what they read.
PATH_READ_TOOLS = frozenset({"read_file", "read_text_file", "read_multiple_files", "view_file", "list_code_definition_names"})

PATH_KEYS = ("path", "file_path", "filepath", "target", "target_file", "filename", "directory", "dir", "root", "cwd")
LIST_KEYS = ("paths", "files", "file_paths", "file")

EVALUATOR_PARTS = frozenset({"answer-key", "blueprint", "evaluator-reference", "assist", ".claude"})
EVALUATOR_PREFIXES = ("IDEAL", "COMPARISON")
SECRET_NAME = re.compile(r"^(\.env(\..+)?|.*\.pem|.*\.key|.*credentials.*\.json|.*\.dpapi)$", re.IGNORECASE)
SECRET_ALLOWED = frozenset({".env.example"})


def block(reason: str) -> int:
    print(f"Blocked by the SI kit guard: {reason}", file=sys.stderr)
    return 2


def requested_mcp_tool(tool_name: str, tool_input: dict) -> str | None:
    """Return the mcp__<server>__<tool> name a call asks for, "" if unresolvable, None if not MCP."""
    if tool_name.startswith("mcp__"):
        return tool_name
    if tool_name == "use_mcp_tool":
        server, tool = tool_input.get("server_name"), tool_input.get("tool_name")
        if isinstance(server, str) and isinstance(tool, str) and server and tool:
            return f"mcp__{server}__{tool}"
        return ""
    if tool_name == "access_mcp_resource":
        return ""  # No MCP resources are declared; resource reads are never allowed.
    return None


def declared_paths(tool_input: dict) -> list[str]:
    paths: list[str] = []
    nested = tool_input.get("args")
    if isinstance(nested, dict):
        paths.extend(declared_paths(nested))
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip())
    for key in LIST_KEYS:
        value = tool_input.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    item = item.get("path") or item.get("file_path")
                if isinstance(item, str) and item.strip():
                    paths.append(item.strip())
    return paths


def _key(text: str) -> str:
    return os.path.normcase(text)


def workspace_parts(raw: str, root: Path) -> tuple[str, ...] | str:
    """Return the path's parts relative to the workspace, or a refusal reason."""
    if "\x00" in raw:
        return "path contains a NUL character"
    if raw.startswith("~"):
        return f"home-relative path is outside the workspace: {raw}"
    pieces = re.split(r"[\\/]+", raw)
    if ".." in pieces:
        return f"path uses '..': {raw}"
    supplied = Path(raw)
    if supplied.drive and not supplied.is_absolute():
        return f"drive-relative path is ambiguous: {raw}"
    target = supplied if supplied.is_absolute() else root / supplied
    try:
        resolved = target.resolve()  # follows symlinks and junctions that exist
    except (OSError, RuntimeError) as exc:
        return f"path cannot be resolved ({exc.__class__.__name__}): {raw}"
    root_key, target_key = _key(str(root)), _key(str(resolved))
    if target_key == root_key:
        return ()
    if not target_key.startswith(root_key.rstrip("\\/") + os.sep):
        return f"path is outside the workspace: {raw}"
    return PurePath(str(resolved)[len(str(root).rstrip("\\/")) + 1:]).parts


def read_refusal(parts: tuple[str, ...], raw: str) -> str | None:
    for part in parts:
        if _key(part) in {_key(p) for p in EVALUATOR_PARTS} or part.upper().startswith(EVALUATOR_PREFIXES):
            return f"folder is not part of the SI workspace: {raw}"
    if parts and SECRET_NAME.match(parts[-1]) and parts[-1].lower() not in SECRET_ALLOWED:
        return f"file looks like a secret: {raw}"
    if any(_key(part) == _key("secrets") for part in parts[:-1]):
        return f"folder looks like a secret store: {raw}"
    return None


def write_refusal(parts: tuple[str, ...], raw: str, *, directory: bool) -> str | None:
    if not parts or _key(parts[0]) != _key("runs"):
        return f"Bob writes only inside runs/<name>/, not {raw}"
    if len(parts) < 2 or not RUN_NAME.fullmatch(parts[1]):
        return f"the run folder name must match [A-Za-z0-9][A-Za-z0-9._-]*: {raw}"
    if len(parts) < 3 and not directory:
        return f"write a file inside runs/<name>/, not the run folder itself: {raw}"
    if any(_key(part) == _key(".git") for part in parts):
        return f"Git metadata is not writable: {raw}"
    return read_refusal(parts, raw)


def main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return block("the PreToolUse payload is not valid JSON")
    if not isinstance(event, dict):
        return block("the PreToolUse payload is not a JSON object")
    tool_name = str(event.get("tool_name") or event.get("tool") or "")
    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    if not tool_name:
        return block("the PreToolUse payload names no tool")

    requested = requested_mcp_tool(tool_name, tool_input)
    if requested is not None:
        if not requested or not MCP_TOOL.fullmatch(requested):
            return block(f"{tool_name} does not name one of the kit's MCP tools")
        if requested not in ALLOWED_MCP_TOOLS:
            return block(f"{requested} is not one of the read-only roster, ratecard, tickets or timesheets tools")
        return 0
    if EXEC_TOOLS.search(tool_name):
        return block(f"{tool_name}: Bob runs no commands in this kit; you run the checkers yourself")
    if DESTRUCTIVE_TOOLS.search(tool_name):
        return block(f"{tool_name}: delete, move and rename are not permitted")

    root = Path.cwd().resolve()
    paths = declared_paths(tool_input)
    if WRITE_TOOLS.search(tool_name):
        if not paths:
            return block(f"{tool_name} did not name a path the guard can check")
        directory = bool(re.search(r"(mkdir|create_dir)", tool_name, re.IGNORECASE))
        for raw in paths:
            parts = workspace_parts(raw, root)
            if isinstance(parts, str):
                return block(parts)
            reason = write_refusal(parts, raw, directory=directory)
            if reason:
                return block(reason)
        return 0
    if not paths:
        if tool_name in ROOTED_READ_TOOLS:
            paths = ["."]
        elif tool_name in PATH_READ_TOOLS:
            return block(f"{tool_name} did not name a path the guard can check")
        else:
            return 0  # e.g. use_skill, ask_followup_question, attempt_completion, switch_mode
    for raw in paths:
        parts = workspace_parts(raw, root)
        if isinstance(parts, str):
            return block(parts)
        reason = read_refusal(parts, raw)
        if reason:
            return block(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
