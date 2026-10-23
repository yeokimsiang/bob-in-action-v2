"""Shared stdio loop for the synthetic read-only mock MCP servers.

Newline-delimited JSON-RPC 2.0 over
stdio with initialize, ping, tools/list and tools/call. Tool descriptors come
from contract.json so the servers, the .bob hook guard and the prompts share
one source of names. There are no write tools and no clocks or randomness, so
every response is a pure function of the request and the pinned datasets.
"""

from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "contract.json"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-11-25")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ToolError(ValueError):
    """A tool-level failure returned to the client as isError content."""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_contract() -> dict:
    return load_json(CONTRACT_PATH)


def load_pinned_dataset(name: str) -> dict:
    """Load a dataset only if its bytes match the SHA-256 pinned in datasets.json."""
    pins = load_json(ROOT / "datasets.json")["datasets"]
    entry = pins[name]
    path = ROOT.parents[1] / entry["path"]
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != entry["sha256"]:
        raise RuntimeError(f"dataset {name} hash mismatch: pinned {entry['sha256']}, actual {actual}")
    return json.loads(raw.decode("utf-8"))


def tool_descriptors(server: str, contract: dict | None = None) -> list[dict]:
    contract = contract or load_contract()
    return contract["servers"][server]["tools"]


def parse_day(value: str, field: str) -> date:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        raise ToolError(f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolError(f"{field} is not a valid date") from exc


def check_arguments(spec: dict, args: dict) -> str | None:
    if any(key not in args for key in spec["required"]):
        return "Invalid tool arguments: missing required argument"
    if any(key not in spec["properties"] for key in args):
        return "Invalid tool arguments: unexpected argument"
    for key, value in args.items():
        if spec["properties"][key].get("type") == "string" and not isinstance(value, str):
            return f"Invalid tool arguments: {key} must be a string"
    return None


def handle(message: object, state: dict, server_name: str, tools: list[dict], invoke: Callable[[str, dict], object]) -> dict | None:
    """Return the JSON-RPC response for one decoded message, or None for notifications."""
    descriptors = {tool["name"]: tool for tool in tools}
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": message.get("id") if isinstance(message, dict) else None, "error": {"code": -32600, "message": "Invalid Request"}}
    if "id" not in message:  # JSON-RPC notifications receive no response.
        return None
    ident = message["id"]
    method = message["method"]

    def ok(result: object) -> dict:
        return {"jsonrpc": "2.0", "id": ident, "result": result}

    def err(code: int, text: str) -> dict:
        return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": text}}

    if method == "initialize":
        params = message.get("params", {})
        if not isinstance(params, dict) or not isinstance(params.get("protocolVersion"), str):
            return err(-32602, "protocolVersion is required")
        state["initialized"] = True
        requested = params["protocolVersion"]
        negotiated = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        return ok({"protocolVersion": negotiated, "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": f"synthetic-mock-{server_name}", "version": "1.0.0"}})
    if not state.get("initialized"):
        return err(-32000, "Initialize first")
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": tools})
    if method == "tools/call":
        params = message.get("params", {})
        if not isinstance(params, dict) or not isinstance(params.get("name"), str) or not isinstance(params.get("arguments", {}), dict):
            return err(-32602, "Invalid tool parameters")
        name = params["name"]
        if name not in descriptors:
            return err(-32602, "Unknown or disabled tool")
        args = params.get("arguments", {})
        problem = check_arguments(descriptors[name]["inputSchema"], args)
        if problem:
            return ok({"content": [{"type": "text", "text": problem}], "isError": True})
        try:
            output = invoke(name, args)
        except (ToolError, KeyError) as exc:
            return ok({"content": [{"type": "text", "text": str(exc)}], "isError": True})
        return ok({"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, sort_keys=True)}],
                   "structuredContent": {"data": output}})
    return err(-32601, "Method not found")


def serve(server_name: str, invoke: Callable[[str, dict], object], stream_in: Iterable[bytes] | None = None, stream_out=None,
          tools: list[dict] | None = None) -> None:
    """Serve until stdin closes; `tools` defaults to the server's descriptors in contract.json."""
    tools = tool_descriptors(server_name) if tools is None else tools
    stream_in = sys.stdin.buffer if stream_in is None else stream_in
    stream_out = sys.stdout.buffer if stream_out is None else stream_out
    state: dict = {}
    for raw in stream_in:
        if not raw.strip():
            continue
        try:
            message = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response: dict | None = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            response = handle(message, state, server_name, tools, invoke)
        if response is not None:
            stream_out.write(json.dumps(response, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n")
            stream_out.flush()
