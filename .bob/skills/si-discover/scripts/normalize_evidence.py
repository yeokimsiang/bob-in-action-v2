"""Check and sort Bob-authored evidence; never infer runtime facts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


CLASSES = {"source_config", "build_test", "runtime", "interview", "inference", "unknown"}
RELATION_KINDS = {"http", "call", "sql", "schedule", "config", "data", "queue", "file", "unknown"}
RUNTIME_STATES = {"observed", "source_inferred", "unknown"}
TICKET_POINTER = "mcp:tickets/"
TICKET_CLASSES = {"interview", "unknown"}
CODE_SUFFIXES = (".java", ".js")
POINTER = re.compile(r"(?P<path>[^:\s]+?)(?::(?P<start>[0-9]+)(?:-(?P<end>[0-9]+))?)?(?:\s.*)?")
DOC_NOTE = re.compile(r"Documentation note \((?P<component>[^)]+)\):")
METHOD_REF = re.compile(r"(?P<owner>[A-Za-z_$][\w$]*)\.(?P<method>[A-Za-z_$][\w$]*)(?:\(\))?")


class SourceCheckError(ValueError):
    """Every source-check violation, reported together."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _code_pointer(pointer: str) -> re.Match[str] | None:
    match = POINTER.fullmatch(pointer.strip())
    if not match or not match.group("path").endswith(CODE_SUFFIXES):
        return None
    return match


def _declares(text: str, method: str) -> bool:
    return re.search(rf"\b{re.escape(method)}\b\s*(?:\(|=|:)", text) is not None


def check_against_source(result: dict, source_root: Path) -> dict:
    """Validate v2 documentation notes and method-level call edges against frozen source."""
    root = source_root.resolve()
    errors: list[str] = []
    lines_by_path: dict[str, list[str]] = {}

    def read(path: str) -> list[str] | None:
        if path in lines_by_path:
            return lines_by_path[path]
        candidate = Path(path)
        resolved = (root / candidate).resolve()
        if candidate.is_absolute() or not resolved.is_relative_to(root):
            errors.append(f"{path}: pointer escapes the source root")
            lines_by_path[path] = None
        elif not resolved.is_file():
            errors.append(f"{path}: cited source file does not exist")
            lines_by_path[path] = None
        else:
            lines_by_path[path] = resolved.read_text(encoding="utf-8-sig").splitlines()
        return lines_by_path[path]

    rows = {row["id"]: row for row in result["evidence"]}
    components: set[str] = set()
    documented: set[str] = set()
    for row in result["evidence"]:
        match = _code_pointer(row["pointer"])
        if not match:
            continue
        path = match.group("path")
        if read(path) is None:
            continue
        components.add(path)
        if DOC_NOTE.match(row["observation"].strip()):
            documented.add(path)
    for path in sorted(components - documented):
        errors.append(f"{path} has no documentation note (observation starting 'Documentation note (<Component>):')")

    # Exact stem first (Desk -> Desk.java, desk -> desk.js); case-insensitive only when unambiguous.
    exact: dict[str, set[str]] = {}
    folded: dict[str, set[str]] = {}
    for path in components:
        exact.setdefault(Path(path).stem, set()).add(path)
        folded.setdefault(Path(path).stem.casefold(), set()).add(path)
    by_stem = {stem: next(iter(paths)) for stem, paths in folded.items() if len(paths) == 1}
    by_stem.update({stem: next(iter(paths)) for stem, paths in exact.items() if len(paths) == 1})
    method_edges = 0
    for relation in result["relationships"]:
        caller = METHOD_REF.fullmatch(relation["from_component"].strip())
        callee = METHOD_REF.fullmatch(relation["to_component"].strip())
        if relation["kind"] != "call" or not caller or not callee:
            continue
        method_edges += 1
        ident = relation["id"]
        for ref in (caller, callee):
            path = by_stem.get(ref.group("owner")) or by_stem.get(ref.group("owner").casefold())
            if path is None:
                errors.append(f"{ident}: component {ref.group('owner')} has no cited source file")
            elif not _declares("\n".join(lines_by_path[path] or []), ref.group("method")):
                errors.append(f"{ident}: {ref.group('owner')}.{ref.group('method')} is not declared in {path}")
        cited = []
        found = False
        for evidence_id in relation["evidence_ids"]:
            match = _code_pointer(rows[evidence_id]["pointer"])
            if not match or not match.group("start"):
                continue
            path, start = match.group("path"), int(match.group("start"))
            end = int(match.group("end") or start)
            cited.append(rows[evidence_id]["pointer"].strip())
            lines = read(path)
            if lines is None:
                continue
            if start < 1 or end < start or end > len(lines):
                errors.append(f"{ident}: line {end if end > len(lines) else start} is outside {path} ({len(lines)} lines)")
                continue
            if re.search(rf"\b{re.escape(callee.group('method'))}\b", "\n".join(lines[start - 1:end])):
                found = True
        if not found:
            errors.append(f"{ident}: no cited line in {', '.join(cited) or 'its evidence'} calls '{callee.group('method')}'")
    if not method_edges:
        errors.append("no method-level call edge (kind 'call' between 'Class.method' names) was recorded")
    if errors:
        raise SourceCheckError(errors)
    return {"checked": True, "documentation_notes": len(documented), "method_call_edges": method_edges,
            "code_components": sorted(components)}


def normalize(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Evidence input requires schema_version 1")
    for field in ("run_id", "source_revision"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(f"Missing {field}")
    rows = payload.get("evidence")
    if not isinstance(rows, list) or not rows:
        raise ValueError("evidence must be a nonempty array")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each evidence row must be an object")
        ident = row.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"EV-[A-Za-z0-9.-]+", ident) or ident in seen:
            raise ValueError("Evidence IDs must be unique EV- identifiers")
        seen.add(ident)
        if not isinstance(row.get("class"), str) or row["class"] not in CLASSES:
            raise ValueError(f"{ident}: unsupported evidence class")
        for field in ("pointer", "observation"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{ident}: missing {field}")
        if not isinstance(row.get("gap"), str):
            raise ValueError(f"{ident}: gap must be text, empty only when no gap is asserted")
        if row["class"] in {"inference", "unknown"} and not row["gap"].strip():
            raise ValueError(f"{ident}: inferred or unknown evidence needs an explicit gap")
        if row["pointer"].strip().startswith(TICKET_POINTER) and (
            row["class"] not in TICKET_CLASSES or not row["gap"].strip()
        ):
            raise ValueError(f"{ident}: ticket evidence is a user report; use class interview or unknown with a gap")
    relationships = payload.get("relationships")
    if not isinstance(relationships, list) or not relationships:
        raise ValueError("relationships must be a nonempty dependency/call-graph array")
    relation_ids = set()
    for row in relationships:
        if not isinstance(row, dict):
            raise ValueError("Each relationship must be an object")
        ident = row.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"REL-[A-Za-z0-9.-]+", ident) or ident in relation_ids:
            raise ValueError("Relationship IDs must be unique REL- identifiers")
        relation_ids.add(ident)
        for field in ("from_component", "to_component"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{ident}: missing {field}")
        if row.get("kind") not in RELATION_KINDS:
            raise ValueError(f"{ident}: unsupported relationship kind")
        references = row.get("evidence_ids")
        if not isinstance(references, list) or not references or any(ref not in seen for ref in references):
            raise ValueError(f"{ident}: relationship evidence does not resolve")
        state = row.get("runtime_status")
        if state not in RUNTIME_STATES:
            raise ValueError(f"{ident}: unsupported runtime_status")
        if not isinstance(row.get("gap"), str):
            raise ValueError(f"{ident}: gap must be text")
        if state != "observed" and not row["gap"].strip():
            raise ValueError(f"{ident}: unobserved relationship needs an explicit gap")
    return {"valid": True, "schema_version": 1, "run_id": payload["run_id"],
            "source_revision": payload["source_revision"], "evidence": sorted(rows, key=lambda row: row["id"]),
            "relationships": sorted(relationships, key=lambda row: row["id"]),
            "semantic_review": "pending"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Factory v2: check documentation notes and method-level call edges against this source tree",
    )
    args = parser.parse_args()
    try:
        raw = args.input.read_bytes()
        result = normalize(json.loads(raw.decode("utf-8-sig")))
        if args.source_root is not None:
            if not args.source_root.is_dir():
                raise ValueError("--source-root must be an existing directory")
            result["source_check"] = check_against_source(result, args.source_root)
        result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    except SourceCheckError as error:
        print(json.dumps({"valid": False, "errors": error.errors}, sort_keys=True))
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
