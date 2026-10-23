---
name: si-plan
description: Plans dependency-aware enterprise migration waves and a bounded feature pilot. Use when estimating work packages, assigning delivery roles or preparing implementation roadmaps.
---

# Dependency-aware planning

Bob authors the plan from accepted findings. This is custom SI planning IP; role labels do not prove independent identities or human approval. Only one separately authorized Java invoice-preview pilot may be implemented; the estate and other targets remain forecasts.

1. Read [the dependency contract](references/dependency-contract.md), the report standard and rubric in `.bob/standards/` and the run's findings. Draft [implementation-plan.md](templates/implementation-plan.md) and [validation-ledger.md](templates/validation-ledger.md) into `runs/<name>/reports/`, sharing IDs with commercial. Include delivery waves, distinct developer/reviewer/tech-lead/QA/PM responsibilities, Git checkpoints and labelled synthetic ticket/wiki evidence.
2. Fill [plan-tasks.json](templates/plan-tasks.json) into `runs/<name>/data/plan-tasks.json` from the same work packages: owner, predecessors, client input, duration basis, exit evidence and status. Give every accepted finding exactly one disposition: `mapped` to the complete WBS list, or explicit `deferred`/`accepted_risk` with owner and reason and no work package. Put the same disposition rows in both the implementation plan and SOW handoff. Effort is total person-hours; duration needs stated capacity/calendars and remains relative/illustrative without client dates.
3. **Checker (the user runs it; Bob has no shell):** after Bob writes, the user runs [validate_dag.py](scripts/validate_dag.py) with Python 3.11+ from the repository root:

   `python .bob/skills/si-plan/scripts/validate_dag.py --input runs/<name>/data/plan-tasks.json --run-id <name> --findings runs/<name>/data/findings.json`

   Delay review: add `--delay WBS-1.1=3`.

   Stdout contains dependency order, critical chain, relative start/finish days and a SHA-256/byte-count descriptor for the exact `plan-tasks.json` bytes parsed. Exit 2 rejects unresolved predecessors, cycles and invalid durations; exit 0 validates arithmetic/structure, not feasibility. The helper writes no files.
4. Three required plan sections are specified in the [dependency contract](references/dependency-contract.md#factory-v2-staffing-and-calibration): per-module work packages with a `Component` column; staffing that maps every WBS to required skills and named synthetic roster people from the roster tools (`mcp__roster__roster_list_people`, `mcp__roster__roster_find_by_skill`, `mcp__roster__roster_availability`), flagging each skills gap; and a velocity calibration protocol that keeps "velocity not calibrated". The ledger records every rubric ID, including Q16–Q21 and B11–B13. The user checks them with `python .bob/skills/si-collate/scripts/validate_report_quality.py --partial-stage plan --pack runs/<name>/reports --plan-tasks runs/<name>/data/plan-tasks.json`.
5. Bob explains the assumptions and hands the plan/WBS to `si-business`. Human approval and production acceptance stay pending unless evidenced.
