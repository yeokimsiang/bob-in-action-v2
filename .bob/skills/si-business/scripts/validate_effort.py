"""Call the existing Decimal WBS formatter without authoring estimates or prose."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


sys.dont_write_bytecode = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON object containing Bob-authored rows")
    parser.add_argument("--formatter", type=Path, default=Path(__file__).resolve().parents[4] / "tools/checkers/effort_model.py",
                        help="Trusted deployed copy of the repository's existing effort formatter")
    parser.add_argument("--csv-output", type=Path, help="New run-authorized CSV path; existing files are refused")
    parser.add_argument("--run-id")
    parser.add_argument("--source-revision")
    parser.add_argument("--plan-tasks", type=Path)
    args = parser.parse_args()
    try:
        input_bytes = args.input.read_bytes()
        payload = json.loads(input_bytes.decode("utf-8-sig"))
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "run_id", "source_revision", "rows"}:
            raise ValueError("Effort input must contain only the exact candidate fields")
        if payload.get("schema_version") != 1:
            raise ValueError("Effort input requires schema_version 1")
        for field, expected in (("run_id", args.run_id), ("source_revision", args.source_revision)):
            value = payload.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be nonempty text")
            if expected is not None and value != expected:
                raise ValueError(f"{field} does not match the value given on the command line")
        if args.plan_tasks:
            plan = json.loads(args.plan_tasks.read_text(encoding="utf-8-sig"))
            tasks = plan.get("tasks") if isinstance(plan, dict) else None
            if not isinstance(tasks, list) or not tasks:
                raise ValueError("Accepted plan sidecar has no tasks")
            expected_pairs = {
                (row.get("wbs_id"), row.get("deliverable_id"))
                for row in tasks if isinstance(row, dict)
            }
            if len(expected_pairs) != len(tasks) or any(
                not isinstance(wbs, str) or not isinstance(deliverable, str)
                for wbs, deliverable in expected_pairs
            ):
                raise ValueError("Accepted plan sidecar has invalid or duplicate WBS/deliverable pairs")
            actual_pairs = {
                (row.get("wbs_id"), row.get("deliverable_id"))
                for row in payload["rows"] if isinstance(row, dict)
            }
            if actual_pairs != expected_pairs:
                raise ValueError("Effort rows must exactly cover accepted WBS/deliverable pairs")
        if not args.formatter.is_file():
            raise ValueError("Trusted effort formatter is unavailable; pass --formatter from the run manifest")
        spec = importlib.util.spec_from_file_location("si_existing_effort_formatter", args.formatter)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load trusted effort formatter")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = {
            "valid": True,
            "run_id": payload["run_id"],
            "source_revision": payload["source_revision"],
            **module.prepare_effort_csv(payload["rows"]),
        }
        csv_bytes = result["csv"].encode("utf-8")
        result["validated_input"] = {
            "name": args.input.name,
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
            "bytes": len(input_bytes),
        }
        result["generated_artifact"] = {
            "name": args.csv_output.name if args.csv_output else "effort-model.csv",
            "sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "bytes": len(csv_bytes),
        }
        if args.csv_output:
            with args.csv_output.open("xb") as output:
                output.write(csv_bytes)
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
