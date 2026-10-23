"""Check report completeness and cross-file traceability without judging truth.

This helper is deliberately narrower than an independent review.  It rejects
unresolved templates, missing client-facing sections, incomplete target/rubric
coverage, and identifiers that drift between the six report artifacts.  Factory
v2 adds section checks for SI-measured debt scoring, seven-path option scoring,
ticket corroboration, per-module staffing, velocity calibration and the
illustrative-price reference, and rejects currency amounts in Bob's prose.  It
does not decide whether evidence supports a claim or whether an estimate is
reasonable.
"""

from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
from pathlib import Path
import re


PACK = (
    "assessment.md",
    "target-annexes.md",
    "effort-model.csv",
    "implementation-plan.md",
    "sow.md",
    "validation-ledger.md",
)
PROFILES = (
    "java-8-to-21",
    "java-to-kotlin",
    "javascript-to-typescript",
    "h2-to-postgresql",
    "monolith-to-preview-service",
    "java-to-fastapi",
    "java-to-aspnet-core",
)
REQUIRED_HEADINGS = {
    "assessment.md": (
        "Recommendation and decision",
        "Current state and inspected evidence",
        "Legacy code health and poor-practice findings",
        "Architecture, dependencies and operations",
        "Security assessment",
        "Options and target tradeoffs",
        "Pilot actuals and future forecasts",
        "Effort, dependencies and unresolved inputs",
        "Decisions, operational gaps and acceptance limits",
    ),
    "implementation-plan.md": (
        "Scope and source of effort",
        "Delivery waves and work packages",
        "Team, responsibilities and sign-offs",
        "Critical dependency chain",
        "Prerequisite delay review",
        "Delivery controls and stakeholder visibility",
        "Risks, exclusions and change control",
    ),
    "sow.md": (
        "Purpose, boundary and exclusions",
        "Deliverables and artifact crosswalk",
        "Effort and relative schedule",
        "Responsibilities and client dependencies",
        "Review, correction and acceptance",
        "Change control and commercial terms",
    ),
    "validation-ledger.md": (
        "Native origin and immutable artifacts",
        "Material claim-to-evidence map",
        "Executed checks and visible failures",
        "Numerical and dependency reconciliation",
        "Adversarial rubric and gate",
        "Pilot observations, forecasts and rollback",
        "Correction history",
    ),
}
PLACEHOLDER = re.compile(r"\{\{[^{}]+\}\}|synthetic-template-replace-before-use", re.IGNORECASE)
ID = {
    "finding": re.compile(r"\bF-[A-Za-z0-9.-]+\b"),
    "evidence": re.compile(r"\bEV-[A-Za-z0-9.-]+\b"),
    "wbs": re.compile(r"\bWBS-[0-9]+\.[0-9]+\b"),
    "deliverable": re.compile(r"\bDEL-[A-Za-z0-9.-]+\b"),
}
FINDING_FIELDS = {
    "id", "title", "category", "impact", "evidence_ids", "severity", "rationale",
    "security_status", "status_evidence_ids", "remediation_options", "decision_owner",
}
EVIDENCE_DISPOSITION_FIELDS = {"evidence_id", "disposition", "finding_ids", "owner", "reason"}
TASK_FIELDS = {
    "wbs_id", "deliverable_id", "finding_ids", "owner_role", "predecessors",
    "client_input", "duration_days", "duration_basis", "exit_evidence", "status",
}
FINDING_DISPOSITION_FIELDS = {"finding_id", "disposition", "wbs_ids", "owner", "reason"}
EFFORT_FIELDS = {
    "deliverable_id", "wbs_id", "task_name", "role", "quantity", "unit", "low_hours",
    "central_hours", "high_hours", "method", "evidence_or_comparable", "uncertainty_driver",
    "included", "status", "notes",
}
DISPOSITIONS = {"mapped", "deferred", "accepted_risk"}
# Factory v2 sections (active plan Task B8).  Each check is structural: it
# proves the section exists and carries its required basis, not that it is true.
V2_SECTIONS = {
    "tech_debt": ("assessment.md", "Technical debt scoring (SI-measured, Bob-scored)"),
    "options": ("assessment.md", "Modernisation options scoring"),
    "tickets": ("assessment.md", "Operational history and ticket corroboration"),
    "security": ("assessment.md", "Security assessment"),
    "components": ("implementation-plan.md", "Work packages by component"),
    "staffing": ("implementation-plan.md", "Staffing and skills coverage"),
    "velocity": ("implementation-plan.md", "Velocity calibration protocol"),
    "roles": ("sow.md", "Rate-card roles and risk drivers"),
    "price": ("sow.md", "Illustrative price reference"),
}
SEVEN_PATHS = ("retire", "retain", "rehost", "relocate", "repurchase", "replatform", "refactor")
TICKET = re.compile(r"\bDESK-[0-9]+\b")
ROSTER_PERSON = re.compile(r"\bSE-[0-9]{2}\b|\bSynthetic Engineer [0-9]{2}\b")
CURRENCY_AMOUNT = re.compile(
    r"(?i)(?:\b(?:SGD|USD|EUR|GBP|AUD)\s?[0-9]|(?:\bS|\bUS)?\$\s?[0-9]|[€£]\s?[0-9]"
    r"|\b[0-9][0-9,]*(?:\.[0-9]+)?\s?(?:SGD|USD|EUR|GBP|AUD)\b)"
)
BOB_MEASURED = re.compile(r"(?i)\bmeasured by Bob\b|\bBob[- ]measured\b")
MARKDOWN_REPORTS = ("assessment.md", "target-annexes.md", "implementation-plan.md", "sow.md", "validation-ledger.md")


def _read_pack(pack: Path) -> dict[str, str]:
    if pack.is_symlink() or not pack.is_dir():
        raise ValueError("pack must be a local directory, not a symlink")
    names = {path.name for path in pack.iterdir()}
    if names != set(PACK):
        raise ValueError(
            f"pack must contain exactly the six artifacts; "
            f"missing={sorted(set(PACK) - names)}; extra={sorted(names - set(PACK))}"
        )
    result: dict[str, str] = {}
    for name in PACK:
        path = pack / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != pack.resolve():
            raise ValueError(f"{name}: must be a contained regular file")
        result[name] = path.read_text(encoding="utf-8")
    return result


def _rubric_ids(rubric: object) -> tuple[set[str], set[str]]:
    if not isinstance(rubric, dict):
        raise ValueError("rubric must be a JSON object")
    criteria = rubric.get("criteria")
    blockers = rubric.get("blockingFailures")
    if not isinstance(criteria, list) or not criteria or not isinstance(blockers, list) or not blockers:
        raise ValueError("rubric requires nonempty criteria and blockingFailures arrays")
    criterion_ids = {row.get("id") for row in criteria if isinstance(row, dict)}
    blocker_ids = {row.get("id") for row in blockers if isinstance(row, dict)}
    if None in criterion_ids or None in blocker_ids or len(criterion_ids) != len(criteria) or len(blocker_ids) != len(blockers):
        raise ValueError("rubric identifiers must be present and unique")
    return criterion_ids, blocker_ids


def _csv_ids(text: str, errors: list[str]) -> tuple[set[str], set[str]]:
    try:
        rows = list(csv.DictReader(StringIO(text, newline="")))
    except csv.Error as error:
        errors.append(f"effort-model.csv: {error}")
        return set(), set()
    if not rows:
        errors.append("effort-model.csv: no data rows")
        return set(), set()
    wbs_ids: set[str] = set()
    deliverable_ids: set[str] = set()
    for number, row in enumerate(rows, 2):
        wbs = (row.get("wbs_id") or "").strip()
        deliverable = (row.get("deliverable_id") or "").strip()
        if not wbs:  # Formatter summary row.
            continue
        if not ID["wbs"].fullmatch(wbs):
            errors.append(f"effort-model.csv row {number}: invalid WBS ID {wbs!r}")
        elif wbs in wbs_ids:
            errors.append(f"effort-model.csv row {number}: duplicate WBS ID {wbs}")
        else:
            wbs_ids.add(wbs)
        if not ID["deliverable"].fullmatch(deliverable):
            errors.append(f"effort-model.csv row {number}: invalid deliverable ID {deliverable!r}")
        else:
            deliverable_ids.add(deliverable)
    if not wbs_ids:
        errors.append("effort-model.csv: no scoped WBS rows")
    return wbs_ids, deliverable_ids


def _load_json(path: Path, label: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: must be a JSON object")
    return payload


def _findings_closure(findings: dict) -> dict:
    if set(findings) != {"schema_version", "run_id", "source_revision", "evidence_ids", "findings", "evidence_dispositions"}:
        raise ValueError("findings.json: exact top-level contract mismatch")
    finding_rows = findings.get("findings")
    evidence_ids = findings.get("evidence_ids")
    evidence_dispositions = findings.get("evidence_dispositions")
    if not isinstance(finding_rows, list) or not finding_rows or not isinstance(evidence_ids, list) or not evidence_ids:
        raise ValueError("findings.json: nonempty findings and evidence_ids are required")
    if len(evidence_ids) != len(set(evidence_ids)) or any(not isinstance(item, str) for item in evidence_ids):
        raise ValueError("findings.json: evidence IDs must be unique text")
    findings_by_id = {}
    for row in finding_rows:
        if not isinstance(row, dict) or set(row) != FINDING_FIELDS:
            raise ValueError("findings.json: each finding must contain only exact fields")
        finding_id = row.get("id")
        if not isinstance(finding_id, str) or finding_id in findings_by_id:
            raise ValueError("findings.json: finding IDs must be unique text")
        references = row.get("evidence_ids")
        status_references = row.get("status_evidence_ids")
        if (
            not isinstance(references, list) or not references
            or not isinstance(status_references, list)
            or set(references + status_references) - set(evidence_ids)
        ):
            raise ValueError(f"findings.json: {finding_id} has unresolved evidence")
        findings_by_id[finding_id] = row
    if not isinstance(evidence_dispositions, list) or len(evidence_dispositions) != len(evidence_ids):
        raise ValueError("findings.json: evidence dispositions must cover every evidence ID")
    evidence_disposition_by_id = {}
    for row in evidence_dispositions:
        if not isinstance(row, dict) or set(row) != EVIDENCE_DISPOSITION_FIELDS:
            raise ValueError("findings.json: evidence disposition exact-field mismatch")
        evidence_id = row.get("evidence_id")
        if evidence_id not in evidence_ids or evidence_id in evidence_disposition_by_id or row.get("disposition") not in DISPOSITIONS:
            raise ValueError("findings.json: invalid or duplicate evidence disposition")
        linked = row.get("finding_ids")
        if not isinstance(linked, list) or set(linked) - set(findings_by_id):
            raise ValueError(f"findings.json: {evidence_id} has unresolved disposition findings")
        actual = {
            finding_id for finding_id, finding in findings_by_id.items()
            if evidence_id in finding["evidence_ids"] or evidence_id in finding["status_evidence_ids"]
        }
        if row["disposition"] == "mapped":
            if set(linked) != actual or not linked or row.get("owner") not in {None, ""} or row.get("reason") not in {None, ""}:
                raise ValueError(f"findings.json: {evidence_id} mapped disposition is incomplete")
        elif linked or actual or not str(row.get("owner") or "").strip() or not str(row.get("reason") or "").strip():
            raise ValueError(f"findings.json: {evidence_id} explicit disposition is incomplete")
        evidence_disposition_by_id[evidence_id] = row
    if set(evidence_disposition_by_id) != set(evidence_ids):
        raise ValueError("findings.json: evidence disposition closure is incomplete")
    return {
        "finding_ids": set(findings_by_id),
        "evidence_ids": set(evidence_ids),
        "evidence_dispositions": evidence_disposition_by_id,
    }


def _plan_closure(plan: dict, finding_ids: set[str]) -> dict:
    if set(plan) != {"schema_version", "run_id", "source_revision", "tasks", "finding_dispositions"}:
        raise ValueError("plan-tasks.json: exact top-level contract mismatch")
    tasks = plan.get("tasks")
    finding_dispositions = plan.get("finding_dispositions")
    if not isinstance(tasks, list) or not tasks or not isinstance(finding_dispositions, list):
        raise ValueError("plan-tasks.json: tasks and finding dispositions are required")
    tasks_by_id = {}
    for row in tasks:
        if not isinstance(row, dict) or set(row) != TASK_FIELDS:
            raise ValueError("plan-tasks.json: each task must contain only exact fields")
        wbs_id = row.get("wbs_id")
        if not isinstance(wbs_id, str) or wbs_id in tasks_by_id:
            raise ValueError("plan-tasks.json: WBS IDs must be unique text")
        if not isinstance(row.get("finding_ids"), list) or set(row["finding_ids"]) - finding_ids:
            raise ValueError(f"plan-tasks.json: {wbs_id} has unresolved findings")
        tasks_by_id[wbs_id] = row
    disposition_by_finding = {}
    for row in finding_dispositions:
        if not isinstance(row, dict) or set(row) != FINDING_DISPOSITION_FIELDS:
            raise ValueError("plan-tasks.json: finding disposition exact-field mismatch")
        finding_id = row.get("finding_id")
        if finding_id not in finding_ids or finding_id in disposition_by_finding or row.get("disposition") not in DISPOSITIONS:
            raise ValueError("plan-tasks.json: invalid or duplicate finding disposition")
        wbs_ids = row.get("wbs_ids")
        if not isinstance(wbs_ids, list) or set(wbs_ids) - set(tasks_by_id):
            raise ValueError(f"plan-tasks.json: {finding_id} has unresolved disposition WBS IDs")
        actual = {wbs_id for wbs_id, task in tasks_by_id.items() if finding_id in task["finding_ids"]}
        if row["disposition"] == "mapped":
            if set(wbs_ids) != actual or not wbs_ids or row.get("owner") not in {None, ""} or row.get("reason") not in {None, ""}:
                raise ValueError(f"plan-tasks.json: {finding_id} mapped disposition is incomplete")
        elif wbs_ids or actual or not str(row.get("owner") or "").strip() or not str(row.get("reason") or "").strip():
            raise ValueError(f"plan-tasks.json: {finding_id} explicit disposition is incomplete")
        disposition_by_finding[finding_id] = row
    if set(disposition_by_finding) != finding_ids:
        raise ValueError("plan-tasks.json: finding disposition closure is incomplete")
    return {
        "tasks": tasks_by_id,
        "finding_dispositions": disposition_by_finding,
        "deliverable_ids": {row["deliverable_id"] for row in tasks_by_id.values()},
    }


def _structured_closure(findings_path: Path, plan_path: Path, effort_path: Path) -> dict:
    findings = _load_json(findings_path, "findings.json")
    plan = _load_json(plan_path, "plan-tasks.json")
    effort = _load_json(effort_path, "effort-rows.json")
    closure = _findings_closure(findings)
    closure.update(_plan_closure(plan, closure["finding_ids"]))
    tasks_by_id = closure["tasks"]

    if set(effort) != {"schema_version", "run_id", "source_revision", "rows"}:
        raise ValueError("effort-rows.json: exact top-level contract mismatch")
    effort_rows = effort.get("rows")
    if not isinstance(effort_rows, list) or not effort_rows:
        raise ValueError("effort-rows.json: nonempty rows are required")
    effort_pairs = []
    for row in effort_rows:
        if not isinstance(row, dict) or set(row) != EFFORT_FIELDS:
            raise ValueError("effort-rows.json: each row must contain only exact fields")
        effort_pairs.append((row.get("wbs_id"), row.get("deliverable_id")))
    task_pairs = {(wbs_id, row.get("deliverable_id")) for wbs_id, row in tasks_by_id.items()}
    if len(effort_pairs) != len(set(effort_pairs)) or set(effort_pairs) != task_pairs:
        raise ValueError("effort-rows.json: rows must exactly cover plan WBS/deliverable pairs")
    identities = {(findings.get("run_id"), findings.get("source_revision")),
                  (plan.get("run_id"), plan.get("source_revision")),
                  (effort.get("run_id"), effort.get("source_revision"))}
    if len(identities) != 1:
        raise ValueError("structured sidecars disagree on run or source identity")
    return closure


def _normalized(value: object) -> str:
    return re.sub(r"[_-]+", " ", str(value)).casefold()


def _prose_only(text: str) -> str:
    """Remove code examples before looking for unresolved authoring tokens."""
    without_fences = re.sub(r"(?s)```.*?```", "", text)
    return re.sub(r"`[^`\n]*`", "", without_fences)


def _heading_present(text: str, heading: str) -> bool:
    numbered = r"(?:[0-9]+(?:\.[0-9]+)*(?:\.|)\s+)?"
    aliases = {
        "Purpose, boundary and exclusions": ("Purpose and authorized boundary",),
        "Change control and commercial terms": ("Scope exclusions and change control",),
        "Native origin and immutable artifacts": ("Source identity and authorization",),
        "Material claim-to-evidence map": ("Assessment and findings evidence coverage",),
        "Executed checks and visible failures": ("Plan artifact completeness check",),
        "Numerical and dependency reconciliation": ("Plan-tasks.json structural checks (pre-validation)",),
        "Adversarial rubric and gate": (
            "Report quality rubric - plan stage coverage",
            "Report quality rubric — plan stage coverage",
        ),
        "Pilot observations, forecasts and rollback": (
            "Client decisions and gaps - open items",
            "Client decisions and gaps — open items",
        ),
    }
    candidates = (heading, *aliases.get(heading, ()))
    exact = bool(re.search(rf"(?mi)^##\s+{numbered}{re.escape(heading)}\s*$", text))
    found = exact or any(
        re.search(rf"(?mi)^##\s+{numbered}{re.escape(candidate)}\s*$", text)
        for candidate in aliases.get(heading, ())
    )
    if heading == "Change control and commercial terms" and found and not exact:
        return bool(re.search(r"(?mi)^#{2,4}\s+(?:[0-9]+(?:\.[0-9]+)*(?:\.|)\s+)?Commercial terms\s*$", text))
    if heading == "Pilot observations, forecasts and rollback" and found and not exact:
        return "pilot" in text.casefold() and "rollback" in text.casefold()
    return found


def _ids_with_ranges(text: str, pattern: re.Pattern[str], prefix: str) -> set[str]:
    """Return explicit IDs plus inclusive integer ranges written with `through`."""
    found = set(pattern.findall(text))
    range_pattern = re.compile(
        rf"\b{re.escape(prefix)}-([0-9]+)\s+through\s+{re.escape(prefix)}-([0-9]+)\b",
        re.IGNORECASE,
    )
    for start_text, end_text in range_pattern.findall(text):
        start, end = int(start_text), int(end_text)
        if end < start or end - start > 1000:
            continue
        width = max(len(start_text), len(end_text))
        found.update(f"{prefix}-{value:0{width}d}" for value in range(start, end + 1))
    return found


def _explicit_wbs_gap(block: str) -> bool:
    normalized = _normalized(block)
    return "planning only" in normalized or "assessment and pilot only" in normalized


def _exact_id(ident: str) -> re.Pattern[str]:
    """Match one ID as a whole token, so F-1 is not found inside F-10 or WBS-1.1 inside WBS-1.10."""
    body = r"[-_ ]+".join(re.escape(part) for part in re.split(r"[-_]+", ident))
    return re.compile(rf"(?<![A-Za-z0-9._-]){body}(?![A-Za-z0-9_]|[.-][A-Za-z0-9])", re.IGNORECASE)


def _has_disposition_row(text: str, ident: str, row: dict, links: list[str]) -> bool:
    required = [_normalized(ident), _normalized(row["disposition"]), *(_normalized(item) for item in links)]
    exact_ids = [_exact_id(item) for item in (ident, *links)]
    for line in text.splitlines():
        normalized = _normalized(line)
        if not all(item in normalized for item in required):
            continue
        if not all(pattern.search(line) for pattern in exact_ids):
            continue
        if row["disposition"] == "mapped":
            return True
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if _normalized(row["owner"]) not in normalized or len(cells) < 5:
            continue
        if cells[-1] and cells[-1].casefold() not in {"none", "null", "n/a", "tbd"}:
            return True
    return False


def _section(text: str, heading: str) -> str | None:
    """Return a level-2 section body (including its subsections), or None."""
    numbered = r"(?:[0-9]+(?:\.[0-9]+)*(?:\.|)\s+)?"
    match = re.search(rf"(?mi)^##\s+{numbered}{re.escape(heading)}\s*$", text)
    if not match:
        return None
    following = re.search(r"(?m)^##\s", text[match.end():])
    return text[match.end():match.end() + following.start()] if following else text[match.end():]


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell):
            continue
        rows.append(cells)
    return rows


def _csv_roles(text: str) -> set[str]:
    try:
        rows = list(csv.DictReader(StringIO(text, newline="")))
    except csv.Error:
        return set()
    return {(row.get("role") or "").strip() for row in rows if (row.get("wbs_id") or "").strip() and (row.get("role") or "").strip()}


def _v2_sections(
    files: dict[str, str],
    closure: dict,
    errors: list[str],
    checks: list[str],
    only: frozenset[str] | None = None,
    scope: tuple[str, ...] = MARKDOWN_REPORTS,
) -> None:
    """Factory v2 structural checks; appended after the v1 checks in a fixed order.

    The final gate passes neither `only` nor `scope` and runs every check on every
    report. The partial mode (PARTIAL_STAGES) selects one stage's checks and limits
    the pack-wide line checks to that stage's own reports; it never changes a rule.
    """
    sections = {
        key: _section(files[name], heading) if name in files else None
        for key, (name, heading) in V2_SECTIONS.items()
    }

    def wanted(check: str) -> bool:
        return only is None or check in only

    def in_scope(key: str) -> bool:
        return V2_SECTIONS[key][0] in scope

    def require(key: str, label: str) -> str:
        name, heading = V2_SECTIONS[key]
        if sections[key] is None:
            errors.append(f"{name}: missing {label} section '## {heading}'")
            return ""
        return sections[key] or ""

    def wbs_rows(body: str, name: str, label: str) -> None:
        listed = {ident for row in _table_rows(body) for cell in row for ident in ID["wbs"].findall(cell)}
        missing = sorted(set(closure["tasks"]) - listed)
        if missing:
            errors.append(f"{name}: {label} table omits accepted WBS IDs {missing}")

    if wanted("tech_debt_scoring_basis"):
        body = require("tech_debt", "tech debt scoring")
        if body:
            lowered = body.casefold()
            if "complexity-metrics.json" not in body:
                errors.append("assessment.md: tech debt scoring must cite the SI-measured input inputs/complexity-metrics.json")
            if "si-measured, bob-scored" not in lowered:
                errors.append("assessment.md: tech debt scoring must carry the label 'SI-measured, Bob-scored'")
            if "rubric" not in lowered:
                errors.append("assessment.md: tech debt scoring must state its scoring rubric")
            if not any(ID["finding"].search(cell) for row in _table_rows(body) for cell in row):
                errors.append("assessment.md: tech debt scoring table must link components to finding IDs")
        for name in scope:
            if BOB_MEASURED.search(files[name]):
                errors.append(f"{name}: complexity is SI-measured, never measured by Bob")
        checks.append("tech_debt_scoring_basis")

    if wanted("modernisation_option_scoring"):
        body = require("options", "modernisation options scoring")
        if body:
            lowered = body.casefold()
            for path in SEVEN_PATHS:
                if not re.search(rf"\b{path}", lowered):
                    errors.append(f"assessment.md: modernisation options scoring does not assess the path '{path}'")
            if "criteria" not in lowered:
                errors.append("assessment.md: modernisation options scoring must state its criteria")
            if "business criticality" not in lowered:
                errors.append("assessment.md: modernisation options scoring must rate business criticality")
        checks.append("modernisation_option_scoring")

    if wanted("ticket_corroboration_only"):
        body = require("tickets", "operational history") if in_scope("tickets") else ""
        if body and "corroboration" not in body.casefold():
            errors.append("assessment.md: operational history must state that tickets are corroboration only")
        for name in scope:
            for line in files[name].splitlines():
                tickets = TICKET.findall(line)
                if tickets and ID["finding"].search(line) and not ID["evidence"].search(line):
                    errors.append(f"{name}: {tickets[0]} cites a finding without primary evidence (tickets are corroboration only)")
        checks.append("ticket_corroboration_only")

    if wanted("source_reading_security_wording"):
        body = sections["security"] or ""
        if "source-reading review, no scanner" not in body.casefold():
            errors.append("assessment.md: security assessment must state 'source-reading review, no scanner'")
        checks.append("source_reading_security_wording")

    if wanted("per_module_work_packages"):
        body = require("components", "work packages by component")
        if body:
            headers = [row for row in _table_rows(body) if any(cell.casefold() == "wbs" for cell in row)]
            if not any(any(cell.casefold().startswith("component") for cell in row) for row in headers):
                errors.append("implementation-plan.md: work packages by component table needs WBS and Component columns")
            wbs_rows(body, "implementation-plan.md", "work packages by component")
        checks.append("per_module_work_packages")

    if wanted("staffing_and_skills_gaps"):
        body = require("staffing", "staffing and skills coverage")
        if body:
            wbs_rows(body, "implementation-plan.md", "staffing")
            if not ROSTER_PERSON.search(body):
                errors.append("implementation-plan.md: staffing must name at least one named synthetic roster person (SE-NN)")
            if "skills gap" not in body.casefold():
                errors.append("implementation-plan.md: staffing must flag each skills gap or state that none was found")
        checks.append("staffing_and_skills_gaps")

    if wanted("velocity_calibration_protocol"):
        body = require("velocity", "velocity calibration protocol")
        if body:
            lowered = body.casefold()
            if "velocity not calibrated" not in lowered:
                errors.append("implementation-plan.md: velocity calibration protocol must keep 'velocity not calibrated'")
            if "pilot" not in lowered:
                errors.append("implementation-plan.md: velocity calibration protocol must say what the pilot measures")
        checks.append("velocity_calibration_protocol")

    if wanted("rate_card_roles_and_risk_drivers"):
        body = require("roles", "rate-card roles and risk drivers")
        if body:
            lowered = body.casefold()
            cells = {cell.strip("`* ").casefold() for row in _table_rows(body) for cell in row}
            for role in sorted(_csv_roles(files["effort-model.csv"])):
                if role.casefold() not in cells:
                    errors.append(f"sow.md: rate-card mapping table omits effort role '{role}' as its own cell")
            if "risk driver" not in lowered:
                errors.append("sow.md: rate-card section must name the chosen risk drivers")
        checks.append("rate_card_roles_and_risk_drivers")

    if wanted("illustrative_price_reference"):
        body = require("price", "illustrative price reference")
        if body:
            lowered = body.casefold()
            for phrase in ("not a quote", "illustrative", "check_effort_numbers.py"):
                if phrase not in lowered:
                    errors.append(f"sow.md: illustrative price reference must include '{phrase}'")
        checks.append("illustrative_price_reference")

    if wanted("no_bob_price_arithmetic"):
        for name in scope:
            match = CURRENCY_AMOUNT.search(files[name])
            if match:
                errors.append(f"{name}: currency amount '{match.group(0)}' in Bob-authored prose; the SI engine owns price arithmetic")
        checks.append("no_bob_price_arithmetic")


def _check_placeholders(files: dict[str, str], names: tuple[str, ...], errors: list[str], checks: list[str]) -> None:
    for name in names:
        if PLACEHOLDER.search(_prose_only(files[name])):
            errors.append(f"{name}: unresolved template placeholder")
    checks.append("no_unresolved_template_placeholders")


def _check_headings(files: dict[str, str], names: tuple[str, ...], errors: list[str], checks: list[str]) -> None:
    for name, headings in REQUIRED_HEADINGS.items():
        if name not in names:
            continue
        text = files[name]
        for heading in headings:
            if not _heading_present(text, heading):
                errors.append(f"{name}: missing required section '{heading}'")
    checks.append("client_facing_sections")


def _check_assessment(assessment: str, closure: dict, errors: list[str], checks: list[str]) -> None:
    finding_ids = set(ID["finding"].findall(assessment))
    evidence_ids = set(ID["evidence"].findall(assessment))
    if not finding_ids:
        errors.append("assessment.md: no stable finding IDs")
    if not evidence_ids:
        errors.append("assessment.md: no stable evidence IDs")
    checks.append("assessment_finding_and_evidence_ids")

    if finding_ids != closure["finding_ids"]:
        errors.append("assessment.md: finding IDs differ from accepted findings sidecar")
    if evidence_ids != closure["evidence_ids"]:
        errors.append("assessment.md: evidence IDs differ from accepted evidence closure")
    for evidence_id, disposition in closure["evidence_dispositions"].items():
        if not _has_disposition_row(assessment, evidence_id, disposition, disposition["finding_ids"]):
            errors.append(f"assessment.md: missing complete evidence disposition row for {evidence_id}")


def _check_annexes(annexes: str, errors: list[str], checks: list[str]) -> None:
    positions: list[tuple[str, int, int]] = []
    for profile in PROFILES:
        matches = list(re.finditer(rf"(?m)^Profile:\s*{re.escape(profile)}\s*$", annexes))
        if len(matches) != 1:
            errors.append(f"target-annexes.md: profile {profile} must appear exactly once")
        else:
            positions.append((profile, matches[0].start(), matches[0].end()))
    if len(positions) == len(PROFILES):
        positions.sort(key=lambda item: item[1])
        for index, (profile, start, _) in enumerate(positions):
            end = positions[index + 1][1] if index + 1 < len(positions) else len(annexes)
            block = annexes[start:end]
            for heading in (
                "Decision and options",
                "Compatibility, behavior and evidence",
                "Delivery, rollback and open decisions",
            ):
                if not re.search(rf"(?mi)^###\s+{re.escape(heading)}\s*$", block):
                    errors.append(f"target-annexes.md: {profile} missing subsection '{heading}'")
            for label, pattern in ID.items():
                if label in {"finding", "evidence", "wbs"} and not pattern.search(block) and not (
                    label == "wbs" and _explicit_wbs_gap(block)
                ):
                    remedy = ": cite a WBS ID or write the words 'planning only'" if label == "wbs" else ""
                    errors.append(f"target-annexes.md: {profile} has no {label} ID{remedy}")
    checks.append("seven_target_annexes")


def _check_plan_crosswalk(plan: str, closure: dict, errors: list[str]) -> None:
    if set(ID["wbs"].findall(plan)) != set(closure["tasks"]):
        errors.append("implementation-plan.md: WBS IDs differ from accepted plan tasks")
    if set(ID["finding"].findall(plan)) != closure["finding_ids"]:
        errors.append("implementation-plan.md: finding IDs differ from accepted finding closure")
    for finding_id, disposition in closure["finding_dispositions"].items():
        if not _has_disposition_row(plan, finding_id, disposition, disposition["wbs_ids"]):
            errors.append(f"implementation-plan.md: missing complete finding disposition row for {finding_id}")


def _check_ledger(
    ledger: str, closure: dict, criterion_ids: set[str], blocker_ids: set[str], errors: list[str], checks: list[str],
) -> None:
    if set(ID["evidence"].findall(ledger)) != closure["evidence_ids"]:
        errors.append("validation-ledger.md: evidence IDs differ from accepted evidence closure")
    checks.append("finding_and_evidence_disposition_closure")

    missing_criteria = sorted(criterion_ids - set(re.findall(r"\bQ[0-9]{2}\b", ledger)))
    missing_blockers = sorted(blocker_ids - set(re.findall(r"\bB[0-9]{2}\b", ledger)))
    if missing_criteria:
        errors.append(f"validation-ledger.md: rubric criteria not recorded {missing_criteria}")
    if missing_blockers:
        errors.append(f"validation-ledger.md: blocking-failure checks not recorded {missing_blockers}")
    checks.append("complete_rubric_record")


def _check_identity(files: dict[str, str], names: tuple[str, ...], errors: list[str], checks: list[str]) -> None:
    for name in names:
        text = files[name]
        for field in ("version", "as_of", "run_id", "source_revision", "kit_version", "author", "status", "synthetic_demo"):
            if not re.search(rf"(?m)^{field}:\s*.+$", text):
                errors.append(f"{name}: frontmatter missing {field}")
    checks.append("report_identity")


def validate(pack_dir: Path, rubric_path: Path, findings_path: Path, plan_path: Path, effort_path: Path) -> dict:
    errors: list[str] = []
    checks: list[str] = []
    try:
        files = _read_pack(pack_dir.resolve())
        rubric = json.loads(rubric_path.read_text(encoding="utf-8-sig"))
        criterion_ids, blocker_ids = _rubric_ids(rubric)
        closure = _structured_closure(findings_path, plan_path, effort_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return {"valid": False, "status": "report_quality_rejected", "errors": [str(error)], "checks": []}

    _check_placeholders(files, PACK, errors, checks)
    _check_headings(files, PACK, errors, checks)
    _check_assessment(files["assessment.md"], closure, errors, checks)
    _check_annexes(files["target-annexes.md"], errors, checks)

    wbs_ids, deliverable_ids = _csv_ids(files["effort-model.csv"], errors)
    plan = files["implementation-plan.md"]
    sow = files["sow.md"]
    missing_plan = sorted(wbs_ids - set(ID["wbs"].findall(plan)))
    missing_sow_wbs = sorted(wbs_ids - set(ID["wbs"].findall(sow)))
    sow_deliverable_ids = _ids_with_ranges(sow, ID["deliverable"], "DEL")
    missing_sow_deliverables = sorted(deliverable_ids - sow_deliverable_ids)
    if missing_plan:
        errors.append(f"implementation-plan.md: missing effort WBS IDs {missing_plan}")
    if missing_sow_wbs:
        errors.append(f"sow.md: missing effort WBS IDs {missing_sow_wbs}")
    if missing_sow_deliverables:
        errors.append(f"sow.md: missing effort deliverable IDs {missing_sow_deliverables}")
    _check_plan_crosswalk(plan, closure, errors)
    if set(ID["wbs"].findall(sow)) != set(closure["tasks"]):
        errors.append("sow.md: WBS IDs differ from accepted plan tasks")
    if sow_deliverable_ids != closure["deliverable_ids"]:
        errors.append("sow.md: deliverable IDs differ from accepted plan tasks")
    if set(ID["finding"].findall(sow)) != closure["finding_ids"]:
        errors.append("sow.md: finding IDs differ from accepted finding closure")
    for finding_id, disposition in closure["finding_dispositions"].items():
        if not _has_disposition_row(sow, finding_id, disposition, disposition["wbs_ids"]):
            errors.append(f"sow.md: missing complete finding disposition row for {finding_id}")
    for artifact in PACK:
        if artifact not in sow:
            errors.append(f"sow.md: deliverable crosswalk omits {artifact}")
    checks.append("wbs_and_deliverable_crosswalk")

    _check_ledger(files["validation-ledger.md"], closure, criterion_ids, blocker_ids, errors, checks)
    _check_identity(files, MARKDOWN_REPORTS, errors, checks)

    _v2_sections(files, closure, errors, checks)

    return {
        "valid": not errors,
        "status": "report_quality_structure_pass" if not errors else "report_quality_rejected",
        "errors": errors,
        "checks": checks,
        "semantic_review": "pending",
        "limits": [
            "Does not establish that evidence supports claims.",
            "Does not establish estimate reasonableness or human approval.",
            "Does not execute pilot, security, browser, database or rollback checks.",
        ],
    }


# Factory v2 earlier checks.  Right after /assess (and /plan) the partner, or Bob through
# the read-only checks tool, runs every final-gate rule whose inputs exist for that stage,
# on that stage's own reports, so a failure is corrected in that stage instead of
# surfacing at the final gate.  The final gate above still runs every check on the
# complete pack; a partial run never reports an error the final gate would not.
PARTIAL_STAGES = {
    "assess": {
        "files": ("assessment.md", "target-annexes.md"),
        "checks": frozenset({
            "tech_debt_scoring_basis", "modernisation_option_scoring", "ticket_corroboration_only",
            "source_reading_security_wording", "no_bob_price_arithmetic",
        }),
    },
    "plan": {
        "files": ("implementation-plan.md", "validation-ledger.md"),
        "checks": frozenset({
            "ticket_corroboration_only", "per_module_work_packages", "staffing_and_skills_gaps",
            "velocity_calibration_protocol", "no_bob_price_arithmetic",
        }),
    },
}


def validate_partial(
    stage: str,
    pack_dir: Path,
    findings_path: Path | None = None,
    plan_path: Path | None = None,
    rubric_path: Path | None = None,
) -> dict:
    """Run one stage's final-gate rules on its own reports; the final gate is still required."""
    errors: list[str] = []
    checks: list[str] = []
    spec = PARTIAL_STAGES.get(stage)
    try:
        if spec is None:
            raise ValueError(f"partial mode supports only {sorted(PARTIAL_STAGES)}")
        if findings_path is None:
            raise ValueError(f"the {stage} partial check needs --findings")
        if stage == "plan" and plan_path is None:
            raise ValueError("the plan partial check needs --plan-tasks")
        if stage == "plan" and rubric_path is None:
            raise ValueError("the plan partial check needs --rubric")
        pack = pack_dir.resolve()
        if pack_dir.is_symlink() or not pack.is_dir():
            raise ValueError("pack must be a local directory, not a symlink")
        files: dict[str, str] = {}
        for name in spec["files"]:
            path = pack / name
            if path.is_symlink() or not path.is_file() or path.resolve().parent != pack:
                raise ValueError(f"{name}: the {stage} partial check needs this contained regular file")
            files[name] = path.read_text(encoding="utf-8")
        findings = _load_json(findings_path, "findings.json")
        closure = _findings_closure(findings)
        closure["tasks"] = {}
        if stage == "plan":
            plan = _load_json(plan_path, "plan-tasks.json")
            closure.update(_plan_closure(plan, closure["finding_ids"]))
            if (findings.get("run_id"), findings.get("source_revision")) != (plan.get("run_id"), plan.get("source_revision")):
                raise ValueError("structured sidecars disagree on run or source identity")
            criterion_ids, blocker_ids = _rubric_ids(json.loads(rubric_path.read_text(encoding="utf-8-sig")))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        return {"valid": False, "status": "report_quality_partial_rejected", "partial_stage": stage,
                "errors": [str(error)], "checks": [], "final_gate": "required"}
    names = spec["files"]
    _check_placeholders(files, names, errors, checks)
    _check_headings(files, names, errors, checks)
    if stage == "assess":
        _check_assessment(files["assessment.md"], closure, errors, checks)
        _check_annexes(files["target-annexes.md"], errors, checks)
    else:
        _check_plan_crosswalk(files["implementation-plan.md"], closure, errors)
        checks.append("wbs_and_deliverable_crosswalk")
        _check_ledger(files["validation-ledger.md"], closure, criterion_ids, blocker_ids, errors, checks)
    _check_identity(files, names, errors, checks)
    _v2_sections(files, closure, errors, checks, only=spec["checks"], scope=names)
    return {
        "valid": not errors,
        "status": "report_quality_partial_pass" if not errors else "report_quality_partial_rejected",
        "partial_stage": stage,
        "errors": errors,
        "checks": checks,
        "final_gate": "required",
        "semantic_review": "pending",
        "limits": [
            f"Runs only the final-gate rules whose inputs exist after {stage}, on the {stage} stage's own reports.",
            "Does not replace the final full report-quality gate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--findings", type=Path)
    parser.add_argument("--plan-tasks", type=Path)
    parser.add_argument("--effort-rows", type=Path)
    parser.add_argument(
        "--partial-stage",
        choices=sorted(PARTIAL_STAGES),
        help="run this stage's final-gate rules right after it (assess needs --findings; plan needs "
             "--findings, --plan-tasks and --rubric); the final gate is still required",
    )
    args = parser.parse_args()
    if args.partial_stage:
        result = validate_partial(args.partial_stage, args.pack, args.findings, args.plan_tasks, args.rubric)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["valid"] else 2
    missing = [
        flag for flag, value in (
            ("--rubric", args.rubric), ("--findings", args.findings),
            ("--plan-tasks", args.plan_tasks), ("--effort-rows", args.effort_rows),
        ) if value is None
    ]
    if missing:
        parser.error("the following arguments are required: " + ", ".join(missing))
    result = validate(args.pack, args.rubric, args.findings, args.plan_tasks, args.effort_rows)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
