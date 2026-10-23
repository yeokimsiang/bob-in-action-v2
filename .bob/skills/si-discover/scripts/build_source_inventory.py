#!/usr/bin/env python3
"""Build a compact, deterministic index of an approved source tree.

The index reduces repetitive agent reads. It is an index, not proof of runtime
usage or a substitute for inspecting the cited source lines.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


TEXT_SUFFIXES = {".css", ".html", ".java", ".js", ".properties", ".xml"}
SENSITIVE_KEY = re.compile(r"(?i)(password|passwd|secret|token|api[._-]?key|credential)")
TYPE_PATTERN = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)")
METHOD_PATTERN = re.compile(
    r"\b(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?[\w<>, ?\[\].]+\s+([A-Za-z_$][\w$]*)\s*\("
)
ROUTE_PATTERN = re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\s*(?:\(\s*)?(?:value\s*=\s*)?[\"']([^\"']*)")
FETCH_PATTERN = re.compile(r"\bfetch\s*\(\s*[`\"']([^`\"']+)")
SQL_PATTERN = re.compile(r"(?i)\b(select|insert|update|delete|create\s+table|alter\s+table)\b")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_hits(lines: list[str], pattern: re.Pattern[str], limit: int = 40) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for number, line in enumerate(lines, 1):
        if pattern.search(line):
            hits.append({"line": number, "text": line.strip()[:240]})
            if len(hits) >= limit:
                break
    return hits


def property_names(lines: list[str]) -> list[dict[str, object]]:
    values: list[dict[str, object]] = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "!")) or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values.append(
            {
                "line": number,
                "key": key.strip(),
                "value": "[REDACTED]" if SENSITIVE_KEY.search(key) else value.strip()[:160],
            }
        )
    return values


def inspect_file(root: Path, path: Path) -> dict[str, object]:
    relative = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    record: dict[str, object] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "lines": len(lines),
        "sha256": sha256(path),
    }
    if path.suffix == ".java":
        record["types"] = sorted(set(TYPE_PATTERN.findall(text)))
        record["methods"] = sorted(set(METHOD_PATTERN.findall(text)))
        record["routes"] = [
            {"verb": match.group(1).upper(), "path": match.group(2)}
            for match in ROUTE_PATTERN.finditer(text)
        ]
        record["imports"] = [
            line.strip().removeprefix("import ").removesuffix(";")
            for line in lines
            if line.strip().startswith("import ")
        ]
    if path.suffix == ".js":
        record["fetch_targets"] = sorted(set(FETCH_PATTERN.findall(text)))
    if path.suffix == ".properties":
        record["properties"] = property_names(lines)
    record["sql_candidates"] = line_hits(lines, SQL_PATTERN)
    record["maintenance_markers"] = line_hits(
        lines,
        re.compile(r"(?i)\b(TODO|FIXME|HACK)\b|catch\s*\(\s*Exception\b|System\.out\.print"),
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Approved source root")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"source root is not a directory: {root}")
    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not path.is_symlink()
    )
    payload = {
        "schema_version": "1.0",
        "root": Path(args.root).as_posix(),
        "limitations": [
            "static source index only",
            "does not prove runtime reachability or production usage",
            "findings require exact source inspection and evidence IDs",
        ],
        "file_count": len(files),
        "total_bytes": sum(path.stat().st_size for path in files),
        "files": [inspect_file(root, path) for path in files],
    }
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
