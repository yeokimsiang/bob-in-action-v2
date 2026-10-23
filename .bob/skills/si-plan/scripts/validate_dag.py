"""Validate dependencies and recompute relative duration under prerequisite delay."""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


NUMBER = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?\Z")
TOP_LEVEL_FIELDS = {"schema_version", "run_id", "source_revision", "tasks", "finding_dispositions"}
TASK_FIELDS = {
    "wbs_id", "deliverable_id", "finding_ids", "owner_role", "predecessors",
    "client_input", "duration_days", "duration_basis", "exit_evidence", "status",
}
FINDING_DISPOSITION_FIELDS = {"finding_id", "disposition", "wbs_ids", "owner", "reason"}
DISPOSITIONS = {"mapped", "deferred", "accepted_risk"}


def decimal(value: object) -> Decimal:
    if not isinstance(value, str) or not NUMBER.fullmatch(value):
        raise ValueError("Durations and delays must be nonnegative decimal strings")
    return Decimal(value)


def validate(
    payload: object,
    delays: dict[str, Decimal],
    *,
    expected_run_id: str | None = None,
    expected_source_revision: str | None = None,
    accepted_finding_ids: set[str] | None = None,
) -> dict:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Plan input requires schema_version 1")
    if set(payload) != TOP_LEVEL_FIELDS:
        raise ValueError("Plan input must contain only the exact candidate fields")
    for field, expected in (("run_id", expected_run_id), ("source_revision", expected_source_revision)):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be nonempty text")
        if expected is not None and value != expected:
            raise ValueError(f"{field} does not match the value given on the command line")
    rows = payload.get("tasks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("tasks must be a nonempty array")
    tasks = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each task must be an object")
        if set(row) != TASK_FIELDS:
            raise ValueError("Each task must contain only the exact task fields")
        ident = row.get("wbs_id")
        if not isinstance(ident, str) or not re.fullmatch(r"WBS-[0-9]+\.[0-9]+", ident) or ident in tasks:
            raise ValueError("Task WBS identifiers must be unique and look like WBS-1.1")
        for field in ("deliverable_id", "owner_role", "client_input", "duration_basis", "exit_evidence", "status"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{ident}: missing {field}")
        finding_ids = row.get("finding_ids")
        if not isinstance(finding_ids, list) or not finding_ids or any(not isinstance(item, str) for item in finding_ids):
            raise ValueError(f"{ident}: finding_ids must be a nonempty text array")
        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError(f"{ident}: duplicate finding ID")
        if accepted_finding_ids is not None and set(finding_ids) - accepted_finding_ids:
            raise ValueError(f"{ident}: finding_ids do not resolve to accepted findings")
        decimal(row.get("duration_days"))
        predecessors = row.get("predecessors")
        if not isinstance(predecessors, list) or any(not isinstance(item, str) for item in predecessors):
            raise ValueError(f"{ident}: predecessors must be an array of WBS IDs")
        if len(predecessors) != len(set(predecessors)):
            raise ValueError(f"{ident}: duplicate predecessor")
        tasks[ident] = row
    if set(delays) - set(tasks):
        raise ValueError("Delay names a missing task")
    for ident, row in tasks.items():
        if set(row["predecessors"]) - set(tasks):
            raise ValueError(f"{ident}: predecessor does not resolve")
    disposition_rows = payload.get("finding_dispositions")
    if not isinstance(disposition_rows, list) or not disposition_rows:
        raise ValueError("finding_dispositions must be a nonempty array")
    dispositions = {}
    mapped_tasks = {
        finding_id: {ident for ident, row in tasks.items() if finding_id in row["finding_ids"]}
        for finding_id in (accepted_finding_ids or {item for row in tasks.values() for item in row["finding_ids"]})
    }
    for row in disposition_rows:
        if not isinstance(row, dict) or set(row) != FINDING_DISPOSITION_FIELDS:
            raise ValueError("Each finding disposition must contain only the exact disposition fields")
        finding_id = row.get("finding_id")
        if (
            not isinstance(finding_id, str)
            or (accepted_finding_ids is not None and finding_id not in accepted_finding_ids)
            or finding_id in dispositions
        ):
            raise ValueError("Finding dispositions require unique accepted finding IDs")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError(f"{finding_id}: unsupported finding disposition")
        wbs_ids = row.get("wbs_ids")
        if not isinstance(wbs_ids, list) or any(not isinstance(item, str) for item in wbs_ids):
            raise ValueError(f"{finding_id}: wbs_ids must be an array")
        if len(wbs_ids) != len(set(wbs_ids)) or set(wbs_ids) - set(tasks):
            raise ValueError(f"{finding_id}: disposition WBS IDs do not resolve")
        owner, reason = row.get("owner"), row.get("reason")
        if not (owner is None or isinstance(owner, str)) or not (reason is None or isinstance(reason, str)):
            raise ValueError(f"{finding_id}: owner and reason must be text or null")
        if disposition == "mapped":
            if set(wbs_ids) != mapped_tasks.get(finding_id, set()) or not wbs_ids:
                raise ValueError(f"{finding_id}: mapped disposition must exactly list its work packages")
            if owner not in {None, ""} or reason not in {None, ""}:
                raise ValueError(f"{finding_id}: mapped disposition must not invent an owner or reason")
        else:
            if wbs_ids or mapped_tasks.get(finding_id):
                raise ValueError(f"{finding_id}: explicit disposition cannot also be mapped to a work package")
            if not isinstance(owner, str) or not owner.strip() or not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"{finding_id}: {disposition} requires an explicit owner and reason")
        dispositions[finding_id] = row
    expected_findings = accepted_finding_ids or set(mapped_tasks)
    if set(dispositions) != expected_findings:
        raise ValueError("Finding dispositions must exactly cover every accepted finding ID")
    order, schedule, chains = [], {}, {}
    while len(order) < len(tasks):
        ready = sorted(ident for ident, row in tasks.items() if ident not in schedule and all(pred in schedule for pred in row["predecessors"]))
        if not ready:
            raise ValueError("Dependency cycle blocks the plan")
        for ident in ready:
            row = tasks[ident]
            critical = max(row["predecessors"], key=lambda pred: (schedule[pred]["finish"], pred), default=None)
            start = schedule[critical]["finish"] if critical else Decimal(0)
            finish = start + decimal(row["duration_days"]) + delays.get(ident, Decimal(0))
            schedule[ident] = {"start": start, "finish": finish}
            chains[ident] = (chains[critical] if critical else []) + [ident]
            order.append(ident)
    final = max(tasks, key=lambda ident: (schedule[ident]["finish"], ident))
    return {"valid": True, "run_id": payload["run_id"], "source_revision": payload["source_revision"],
            "wbs_ids": sorted(tasks), "deliverable_ids": sorted({row["deliverable_id"] for row in tasks.values()}),
            "topological_order": order, "critical_dependency_chain": chains[final],
            "elapsed_days": format(schedule[final]["finish"], "f"), "duration_status": "relative_illustrative",
            "schedule": {ident: {"start_day": format(values["start"], "f"), "finish_day": format(values["finish"], "f")} for ident, values in schedule.items()},
            "finding_dispositions": {
                status: sorted(ident for ident, row in dispositions.items() if row["disposition"] == status)
                for status in sorted(DISPOSITIONS)
            }}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--delay", action="append", default=[], metavar="WBS-ID=DAYS")
    parser.add_argument("--run-id")
    parser.add_argument("--source-revision")
    parser.add_argument("--findings", type=Path)
    args = parser.parse_args()
    try:
        input_bytes = args.input.read_bytes()
        delays = {}
        for item in args.delay:
            ident, value = item.split("=", 1)
            if ident in delays:
                raise ValueError("Duplicate delay identifier")
            delays[ident] = decimal(value)
        accepted_findings = None
        if args.findings:
            findings = json.loads(args.findings.read_text(encoding="utf-8-sig"))
            rows = findings.get("findings") if isinstance(findings, dict) else None
            if not isinstance(rows, list) or not rows:
                raise ValueError("Accepted findings sidecar has no findings")
            accepted_findings = {
                row.get("id") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)
            }
            if len(accepted_findings) != len(rows):
                raise ValueError("Accepted findings sidecar has invalid or duplicate IDs")
        result = validate(
            json.loads(input_bytes.decode("utf-8-sig")),
            delays,
            expected_run_id=args.run_id,
            expected_source_revision=args.source_revision,
            accepted_finding_ids=accepted_findings,
        )
        result["validated_input"] = {
            "name": args.input.name,
            "sha256": hashlib.sha256(input_bytes).hexdigest(),
            "bytes": len(input_bytes),
        }
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps({"valid": False, "errors": [str(error)]}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
