"""SI-measured complexity metrics for Java sources (standard library only).

Computes, per Java file under a source root (default app/src, excluding any
target/ directory): physical, blank, comment-only and code line counts, method
count, and per-method branch counts for if, for, while, case, catch, &&, || and
the ternary ?. Output is deterministic JSON with each source file's SHA-256 and
no timestamps, so identical sources always give identical bytes.

This is a lexical approximation, not a compiler: comments, string, text-block
and char literals are blanked before counting, and methods are recognised as
brace blocks whose header looks like a declaration directly inside a type body
(including constructors and methods of anonymous classes). Lambdas and nested
blocks count towards their enclosing method.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "si-complexity-metrics/v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "app" / "src"
EXCLUDED_DIRS = {"target"}
BRANCH_KINDS = ("if", "for", "while", "case", "catch", "&&", "||", "?:")
CONTROL_WORDS = {"if", "for", "while", "switch", "catch", "synchronized", "try", "else", "do", "return", "new", "throw", "finally"}
TYPE_RE = re.compile(r"\b(class|interface|enum|record)\b")
ANNOTATION_RE = re.compile(r"@\s*[\w.]+(\s*\((?:[^()]|\([^()]*\))*\))?")
ANON_CLASS_RE = re.compile(r"\bnew\s+[\w.<>?,\s\[\]]+\((?:[^()]|\([^()]*\))*\)\s*$")
METHOD_RE = re.compile(r"(\w+)\s*\((?:[^()]|\([^()]*\))*\)\s*(?:throws\s+[\w.,\s<>]+)?\s*$")
WORD_BRANCH_RE = re.compile(r"\b(if|for|while|case|catch)\b")
TERNARY_RE = re.compile(r"\?")


def blank_non_code(text: str) -> tuple[str, list[bool]]:
    """Blank comments and literals (keeping newlines); also flag lines holding comment text."""
    out = list(text)
    comment_lines: set[int] = set()
    i, n, line = 0, len(text), 0

    def blank(start: int, end: int, is_comment: bool) -> None:
        nonlocal line
        for k in range(start, end):
            if text[k] == "\n":
                line += 1
            else:
                if is_comment and not text[k].isspace():
                    comment_lines.add(line)
                out[k] = " "

    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            blank(i, end, True)
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            blank(i, end, True)
            i = end
        elif text.startswith('"""', i):
            end = text.find('"""', i + 3)
            end = n if end == -1 else end + 3
            blank(i + 1, end - 1, False)  # Keep delimiters so the line still counts as code.
            i = end
        elif ch in ('"', "'"):
            k = i + 1
            while k < n and text[k] != ch and text[k] != "\n":
                k += 2 if text[k] == "\\" else 1
            end = min(k + 1, n)
            blank(i + 1, max(i + 1, end - 1), False)
            i = end
        else:
            i += 1
    total_lines = text.count("\n") + 1
    return "".join(out), [idx in comment_lines for idx in range(total_lines)]


def count_branches(code: str) -> dict[str, int]:
    counts = dict.fromkeys(BRANCH_KINDS, 0)
    for match in WORD_BRANCH_RE.finditer(code):
        counts[match.group(1)] += 1
    counts["&&"] = code.count("&&")
    counts["||"] = code.count("||")
    for match in TERNARY_RE.finditer(code):
        before = code[:match.start()].rstrip()[-1:]
        after = code[match.end():].lstrip()
        if before in ("<", ",") or after[:1] in (">", ",") or re.match(r"(extends|super)\b", after):
            continue  # Generic wildcard, not a conditional operator.
        counts["?:"] += 1
    return counts


def analyse_source(text: str) -> dict:
    code, comment_flags = blank_non_code(text)
    lines = text.split("\n")
    code_lines = code.split("\n")
    has_code = [bool(c.strip()) for c in code_lines]
    blank = sum(1 for raw in lines if not raw.strip())
    comment_only = sum(1 for idx, raw in enumerate(lines) if raw.strip() and not has_code[idx] and comment_flags[idx])
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def line_of(offset: int) -> int:
        return bisect_right(line_starts, offset)  # 1-based

    methods = []
    stack: list[tuple[str, dict | None]] = []  # (kind, method record) per open brace
    segment_start = 0
    for i, ch in enumerate(code):
        if ch == "{":
            header = code[segment_start:i]
            parent = stack[-1][0] if stack else "file"
            stripped = ANNOTATION_RE.sub(lambda m: " " * len(m.group(0)), header)
            kind, record = "block", None
            if TYPE_RE.search(stripped) and parent in ("file", "type"):
                kind = "type"
            elif ANON_CLASS_RE.search(stripped):
                kind = "type"
            elif parent == "type":
                match = METHOD_RE.search(stripped)
                if match and match.group(1) not in CONTROL_WORDS and "=" not in stripped and "->" not in stripped:
                    kind = "method"
                    name_offset = segment_start + match.start(1)
                    record = {"name": match.group(1), "start_line": line_of(name_offset), "body_start": i}
            stack.append((kind, record))
            segment_start = i + 1
        elif ch == "}":
            if stack:
                kind, record = stack.pop()
                if kind == "method" and record is not None:
                    end_line = line_of(i)
                    body = code[record.pop("body_start") + 1:i]
                    branches = count_branches(body)
                    record.update({
                        "end_line": end_line,
                        "loc": sum(1 for idx in range(record["start_line"] - 1, end_line) if has_code[idx]),
                        "branch_count": sum(branches.values()),
                        "branches": branches,
                    })
                    methods.append(record)
            segment_start = i + 1
        elif ch == ";":
            segment_start = i + 1
    methods.sort(key=lambda m: (m["start_line"], m["name"]))
    return {
        "lines_total": len(lines) - (1 if text.endswith("\n") else 0),
        "lines_blank": blank - (1 if text.endswith("\n") else 0),
        "lines_comment_only": comment_only,
        "lines_code": sum(has_code),
        "method_count": len(methods),
        "max_method_branch_count": max((m["branch_count"] for m in methods), default=0),
        "methods": methods,
    }


def java_files(root: Path) -> list[Path]:
    return sorted((p for p in root.rglob("*.java") if not EXCLUDED_DIRS.intersection(p.relative_to(root).parts)),
                  key=lambda p: p.relative_to(root).as_posix())


def compute(root: Path = DEFAULT_ROOT) -> dict:
    root = root.resolve()
    files = []
    for path in java_files(root):
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n")
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            rel = path.relative_to(root).as_posix()
        files.append({"path": rel, "sha256": hashlib.sha256(raw).hexdigest(), **analyse_source(text)})
    try:
        root_label = root.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        root_label = root.name
    return {
        "schema": SCHEMA,
        "label": "SI-measured",
        "generator": "tools/metrics/complexity_metrics.py",
        "source_root": root_label,
        "excluded_dirs": sorted(EXCLUDED_DIRS),
        "rules": {
            "lines_code": "physical lines with any character left after blanking comments and literals",
            "method": "brace block whose header is a declaration directly inside a class, interface, enum, record or anonymous class body; constructors included",
            "branch_count": "occurrences of if, for, while, case, catch, &&, || and ternary ? inside the method body (else-if counts once as if; do-while once as while; default not counted)",
            "accuracy": "lexical approximation, not a compiler parse",
        },
        "totals": {
            "files": len(files),
            "lines_code": sum(f["lines_code"] for f in files),
            "methods": sum(f["method_count"] for f in files),
            "branches": sum(m["branch_count"] for f in files for m in f["methods"]),
        },
        "files": files,
    }


def render(result: dict) -> bytes:
    return (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute SI-measured Java complexity metrics.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="source root (default app/src)")
    parser.add_argument("--out", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args(argv)
    payload = render(compute(args.root))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.out.with_suffix(args.out.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(args.out)
        print(f"{args.out} sha256={hashlib.sha256(payload).hexdigest()}", file=sys.stderr)
    else:
        sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
