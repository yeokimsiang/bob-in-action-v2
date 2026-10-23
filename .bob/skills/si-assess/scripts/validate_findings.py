"""Validate finding IDs, evidence references and security-status support."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile


CATEGORIES = {
    "documentation", "coupling", "dead_code_candidate", "duplication", "testability",
    "error_data_handling", "obsolete_dependency", "security", "operations", "architecture", "other",
}
TOP_LEVEL_FIELDS = {
    "schema_version", "run_id", "source_revision", "evidence_ids", "findings",
    "evidence_dispositions",
}
FINDING_FIELDS = {
    "id", "title", "category", "impact", "evidence_ids", "severity", "rationale",
    "security_status", "status_evidence_ids", "remediation_options", "decision_owner",
}
EVIDENCE_DISPOSITION_FIELDS = {"evidence_id", "disposition", "finding_ids", "owner", "reason"}
DISPOSITIONS = {"mapped", "deferred", "accepted_risk"}
SEVERITIES = {"critical", "high", "medium", "low", "informational", "unknown"}


def _descriptor(raw: bytes) -> dict[str, object]:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def normalize_evidence_closure(payload: object) -> list[dict[str, object]]:
    """Mirror Bob-declared evidence links across redundant relation lists.

    This takes the union of links Bob already wrote in finding evidence arrays
    or mapped disposition rows. It does not create IDs, alter prose, or resolve
    deferred/accepted-risk conflicts. Strict validation still runs afterwards.
    """
    if not isinstance(payload, dict):
        return []
    findings = payload.get("findings")
    dispositions = payload.get("evidence_dispositions")
    if not isinstance(findings, list) or not isinstance(dispositions, list):
        return []
    by_id: dict[str, dict] = {}
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("id"), str):
            return []
        finding_id = finding["id"]
        if finding_id in by_id:
            return []
        by_id[finding_id] = finding

    changes: list[dict[str, object]] = []
    for disposition in dispositions:
        if not isinstance(disposition, dict) or disposition.get("disposition") != "mapped":
            continue
        evidence_id = disposition.get("evidence_id")
        linked = disposition.get("finding_ids")
        if not isinstance(evidence_id, str) or not isinstance(linked, list):
            continue
        if any(not isinstance(finding_id, str) or finding_id not in by_id for finding_id in linked):
            continue

        declared = set(linked)
        referenced: set[str] = set()
        for finding_id, finding in by_id.items():
            evidence_ids = finding.get("evidence_ids")
            status_ids = finding.get("status_evidence_ids")
            if not isinstance(evidence_ids, list) or not isinstance(status_ids, list):
                continue
            if evidence_id in evidence_ids or evidence_id in status_ids:
                referenced.add(finding_id)

        # An empty mapping is a substantive omission and must still fail.
        closure = declared | referenced
        if not closure:
            continue
        for finding_id in sorted(declared - referenced):
            finding = by_id[finding_id]
            evidence_ids = finding.get("evidence_ids")
            status_ids = finding.get("status_evidence_ids")
            if not isinstance(evidence_ids, list) or not isinstance(status_ids, list):
                continue
            if evidence_id not in evidence_ids and evidence_id not in status_ids:
                before = list(evidence_ids)
                evidence_ids.append(evidence_id)
                evidence_ids.sort()
                changes.append({
                    "path": f"findings/{finding_id}/evidence_ids",
                    "operation": "mirror_declared_mapping",
                    "before": before,
                    "after": list(evidence_ids),
                })

        complete = sorted(closure)
        if linked != complete:
            before = list(linked)
            disposition["finding_ids"] = complete
            changes.append({
                "path": f"evidence_dispositions/{evidence_id}/finding_ids",
                "operation": "mirror_finding_references",
                "before": before,
                "after": complete,
            })
    return changes


def _declared_severity_rows(assessment_text: str) -> dict[str, tuple[int, str]]:
    """Read explicit ordinal-number to label declarations from Bob's finding table."""
    declarations: dict[str, tuple[int, str]] = {}
    scale: dict[int, str] = {}
    for line in assessment_text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.fullmatch(r"F-[A-Za-z0-9.-]+", cells[0]):
            continue
        match = re.match(
            r"^([0-9]+)\s*[\N{EM DASH}\N{EN DASH}-]\s*"
            r"(critical|high|medium|low|informational|unknown)\b",
            cells[3],
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        number = int(match.group(1))
        label = match.group(2).lower()
        previous = scale.get(number)
        if previous is not None and previous != label:
            raise ValueError(
                f"Assessment declares conflicting labels for severity ordinal {number}: "
                f"{previous} and {label}"
            )
        scale[number] = label
        declarations[cells[0]] = (number, label)
    return declarations


def normalize_declared_severity(payload: object, assessment_text: str) -> list[dict[str, object]]:
    """Canonicalize numeric severities only when Bob declared the exact mapping in prose."""
    if not isinstance(payload, dict) or not isinstance(payload.get("findings"), list):
        return []
    declarations = _declared_severity_rows(assessment_text)
    changes: list[dict[str, object]] = []
    for finding in payload["findings"]:
        if not isinstance(finding, dict) or not isinstance(finding.get("id"), str):
            continue
        severity = finding.get("severity")
        if isinstance(severity, bool):
            continue
        if isinstance(severity, int):
            number = severity
        elif isinstance(severity, str) and re.fullmatch(r"[0-9]+", severity):
            number = int(severity)
        else:
            continue
        finding_id = finding["id"]
        declaration = declarations.get(finding_id)
        if declaration is None:
            raise ValueError(
                f"{finding_id}: numeric severity {number} has no explicit Markdown ordinal declaration"
            )
        declared_number, label = declaration
        if declared_number != number:
            raise ValueError(
                f"{finding_id}: JSON severity {number} conflicts with Markdown ordinal {declared_number}"
            )
        finding["severity"] = label
        changes.append({
            "path": f"findings/{finding_id}/severity",
            "operation": "canonicalize_declared_ordinal_severity",
            "before": severity,
            "after": label,
        })
    return changes


def _atomic_write_json(path: Path, payload: object) -> bytes:
    raw = (json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(raw)
    temporary.replace(path)
    return raw


def validate(
    payload: object,
    *,
    expected_run_id: str | None = None,
    expected_source_revision: str | None = None,
    accepted_evidence_ids: set[str] | None = None,
    ticket_evidence_ids: set[str] | None = None,
) -> dict:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Findings input requires schema_version 1")
    if set(payload) != TOP_LEVEL_FIELDS:
        raise ValueError("Findings input must contain only the exact candidate fields")
    for field, expected in (("run_id", expected_run_id), ("source_revision", expected_source_revision)):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be nonempty text")
        if expected is not None and value != expected:
            raise ValueError(f"{field} does not match the value given on the command line")
    known = payload.get("evidence_ids")
    if not isinstance(known, list) or not known or any(not isinstance(item, str) or not item for item in known):
        raise ValueError("evidence_ids must be a nonempty array of identifiers")
    if len(known) != len(set(known)):
        raise ValueError("evidence_ids must be unique")
    if accepted_evidence_ids is not None and set(known) != accepted_evidence_ids:
        raise ValueError("evidence_ids must exactly match accepted discovery evidence")
    rows = payload.get("findings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("findings must be a nonempty array")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each finding must be an object")
        if set(row) != FINDING_FIELDS:
            raise ValueError("Each finding must contain only the exact finding fields")
        ident = row.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"F-[A-Za-z0-9.-]+", ident) or ident in seen:
            raise ValueError("Finding IDs must be unique F- identifiers")
        seen.add(ident)
        for field in ("title", "rationale"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"{ident}: missing {field}")
        if not isinstance(row.get("severity"), str) or row["severity"] not in SEVERITIES:
            raise ValueError(f"{ident}: severity must use the declared ordinal categories")
        if row.get("category") not in CATEGORIES:
            raise ValueError(f"{ident}: category must use the declared legacy-health categories")
        if not isinstance(row.get("impact"), str) or not row["impact"].strip():
            raise ValueError(f"{ident}: impact must explain the business or operational consequence")
        options = row.get("remediation_options")
        if not isinstance(options, list) or not options or any(not isinstance(option, str) or not option.strip() for option in options):
            raise ValueError(f"{ident}: remediation_options must be a nonempty text array")
        if not isinstance(row.get("decision_owner"), str) or not row["decision_owner"].strip():
            raise ValueError(f"{ident}: decision_owner must be explicit, pending when unauthenticated")
        references = row.get("evidence_ids")
        if not isinstance(references, list) or not references or any(not isinstance(ref, str) or ref not in known for ref in references):
            raise ValueError(f"{ident}: finding evidence does not resolve")
        if ticket_evidence_ids is not None and set(references) <= ticket_evidence_ids:
            raise ValueError(f"{ident}: ticket evidence is corroboration only; cite primary source evidence too")
        status = row.get("security_status", "not_applicable")
        if not isinstance(status, str) or status not in {"not_applicable", "under_investigation", "not_affected", "fixed", "unreachable", "exploitable"}:
            raise ValueError(f"{ident}: unsupported security_status")
        status_refs = row.get("status_evidence_ids", [])
        if not isinstance(status_refs, list) or any(not isinstance(ref, str) or ref not in known for ref in status_refs):
            raise ValueError(f"{ident}: security status evidence does not resolve")
        if status not in {"not_applicable", "under_investigation"} and not status_refs:
            raise ValueError(f"{ident}: {status} requires separately recorded status evidence")
    disposition_rows = payload.get("evidence_dispositions")
    if not isinstance(disposition_rows, list) or not disposition_rows:
        raise ValueError("evidence_dispositions must be a nonempty array")
    dispositions = {}
    finding_references = {
        ident: {
            row["id"]
            for row in rows
            if ident in row["evidence_ids"] or ident in row["status_evidence_ids"]
        }
        for ident in known
    }
    for row in disposition_rows:
        if not isinstance(row, dict) or set(row) != EVIDENCE_DISPOSITION_FIELDS:
            raise ValueError("Each evidence disposition must contain only the exact disposition fields")
        evidence_id = row.get("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id not in known or evidence_id in dispositions:
            raise ValueError("Evidence dispositions require unique accepted evidence IDs")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            raise ValueError(f"{evidence_id}: unsupported evidence disposition")
        linked = row.get("finding_ids")
        if not isinstance(linked, list) or any(not isinstance(item, str) for item in linked):
            raise ValueError(f"{evidence_id}: finding_ids must be an array of finding IDs")
        if len(linked) != len(set(linked)) or set(linked) - seen:
            raise ValueError(f"{evidence_id}: disposition finding IDs do not resolve")
        owner, reason = row.get("owner"), row.get("reason")
        if not (owner is None or isinstance(owner, str)) or not (reason is None or isinstance(reason, str)):
            raise ValueError(f"{evidence_id}: owner and reason must be text or null")
        if disposition == "mapped":
            if set(linked) != finding_references[evidence_id]:
                raise ValueError(f"{evidence_id}: mapped disposition must exactly list referencing findings")
            if not linked:
                raise ValueError(f"{evidence_id}: mapped disposition requires a referencing finding")
            if owner not in {None, ""} or reason not in {None, ""}:
                raise ValueError(f"{evidence_id}: mapped disposition must not invent an owner or reason")
        else:
            if linked or finding_references[evidence_id]:
                raise ValueError(f"{evidence_id}: explicit disposition cannot also be mapped to findings")
            if not isinstance(owner, str) or not owner.strip() or not isinstance(reason, str) or not reason.strip():
                raise ValueError(f"{evidence_id}: {disposition} requires an explicit owner and reason")
        dispositions[evidence_id] = row
    if set(dispositions) != set(known):
        raise ValueError("Evidence dispositions must exactly cover every accepted evidence ID")
    checks = ["unique_ids", "evidence_references", "legacy_health_category", "impact_and_options",
              "ordinal_severity", "security_status_evidence", "evidence_disposition_closure"]
    if ticket_evidence_ids is not None:
        checks.append("ticket_corroboration_only")
    return {"valid": True, "run_id": payload["run_id"], "source_revision": payload["source_revision"],
            "finding_ids": sorted(seen), "evidence_ids": sorted(known), "semantic_review": "pending",
            "checks": checks,
            "evidence_dispositions": {
                status: sorted(ident for ident, row in dispositions.items() if row["disposition"] == status)
                for status in sorted(DISPOSITIONS)
            }}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--source-revision")
    parser.add_argument("--evidence-map", type=Path)
    parser.add_argument("--assessment", type=Path)
    parser.add_argument(
        "--normalize-evidence-closure",
        action="store_true",
        help="Mirror only Bob-declared evidence links across redundant relation arrays before strict validation",
    )
    parser.add_argument(
        "--normalize-declared-severity",
        action="store_true",
        help="Canonicalize numeric severities only from matching declarations in Bob's assessment table",
    )
    args = parser.parse_args()
    try:
        input_bytes = args.input.read_bytes()
        original_descriptor = _descriptor(input_bytes)
        payload = json.loads(input_bytes.decode("utf-8-sig"))
        changes: list[dict[str, object]] = []
        if args.normalize_declared_severity:
            if not args.assessment:
                raise ValueError("Declared-severity normalization requires --assessment")
            assessment_text = args.assessment.read_text(encoding="utf-8-sig")
            changes.extend(normalize_declared_severity(payload, assessment_text))
        if args.normalize_evidence_closure:
            changes.extend(normalize_evidence_closure(payload))
        accepted = None
        tickets = None
        if args.evidence_map:
            evidence_map = json.loads(args.evidence_map.read_text(encoding="utf-8-sig"))
            rows = evidence_map.get("evidence") if isinstance(evidence_map, dict) else None
            if not isinstance(rows, list) or not rows:
                raise ValueError("Accepted evidence map has no evidence rows")
            accepted = {
                row.get("id") for row in rows if isinstance(row, dict) and isinstance(row.get("id"), str)
            }
            if len(accepted) != len(rows):
                raise ValueError("Accepted evidence map has invalid or duplicate evidence IDs")
            tickets = {
                row["id"] for row in rows
                if isinstance(row.get("pointer"), str) and row["pointer"].strip().startswith("mcp:tickets/")
            }
        result = validate(
            payload,
            expected_run_id=args.run_id,
            expected_source_revision=args.source_revision,
            accepted_evidence_ids=accepted,
            ticket_evidence_ids=tickets,
        )
        # Preserve the exact Bob candidate on any later validation failure.
        # Normalized bytes become authoritative only after the whole contract passes.
        if changes:
            input_bytes = _atomic_write_json(args.input, payload)
        if args.normalize_evidence_closure or args.normalize_declared_severity:
            result["normalization"] = {
                "type": (
                    "declared_ordinal_severity_and_evidence_closure"
                    if args.normalize_declared_severity and args.normalize_evidence_closure
                    else "declared_ordinal_severity"
                    if args.normalize_declared_severity
                    else "bidirectional_evidence_closure"
                ),
                "applied": bool(changes),
                "before": original_descriptor,
                "after": _descriptor(input_bytes),
                "changes": changes,
            }
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
