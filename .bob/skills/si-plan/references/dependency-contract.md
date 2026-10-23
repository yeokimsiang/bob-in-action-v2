# Dependency and duration contract

Read this while linking implementation-plan.md to findings, effort-model.csv and SOW deliverables. The plan uses the same WBS IDs and declared meanings; an artifact ID must not also name a work item.

## Structured tasks

[plan-tasks.json](../templates/plan-tasks.json) contains `schema_version: 1`, nonempty `tasks` and `finding_dispositions`. Each task has only the declared keys and requires a unique `wbs_id` such as `WBS-1.1`, `owner_role`, `predecessors` array, `client_input`, decimal-string `duration_days`, `duration_basis`, `exit_evidence` and `status`. Every accepted finding appears exactly once in `finding_dispositions`: `mapped` names its exact WBS set and has null owner/reason; `deferred` or `accepted_risk` has no WBS and requires owner and reason. An accepted-risk row is not proof of client acceptance without authenticated evidence. Use explicit `none required` for an inspected no-input conclusion; empty text is not a missing-data substitute. Finding/deliverable/acceptance IDs and low/central/high effort must reconcile to the effort source.

Durations are elapsed working-day assumptions, not labor hours. The helper computes earliest starts from predecessor finishes and duration, allowing independent tasks to overlap only in this arithmetic model. It does not infer staff availability, weekends, actual calendars or client dates. Label its output `relative_illustrative` in the plan until capacity and calendar evidence exist.

## Delay review

[validate_dag.py](../scripts/validate_dag.py) uses exact Decimal arithmetic, rejects missing or duplicate task IDs/predecessors and cycles, and deterministically lists a critical dependency chain. `--delay WBS-1.1=3` adds three elapsed days to that task's finish, delaying downstream starts; repeat the flag for different tasks. Compare baseline and delayed gate windows in the actual plan. A separate independent branch must remain unchanged. A tied critical chain is resolved consistently by identifier, not treated as unique analytical certainty.

## Factory v2 staffing and calibration

`implementation-plan.md` adds three level-2 sections with exact headings. Each section's table lists every accepted WBS ID; the report-quality gate checks this.

- **`## Work packages by component`:** columns `WBS`, `Component`, `Owner role`, `Duration days` and `Effort basis`. Components use the discovery map's names; use `cross-cutting` when a package spans modules. `Duration days` repeats the `plan-tasks.json` value and is not labor hours.
- **`## Staffing and skills coverage`:** read the synthetic roster through the governed read-only roster tools.
  - Give each WBS its required skills, the named synthetic people (`SE-NN Synthetic Engineer NN`) who hold them, their availability window and a skills-gap cell.
  - Flag every gap, or state `skills gap: none found`.
  - Roster people are placeholders, not staff, and assignment stays a proposal pending the resourcing owner.
  - If the tools are unavailable, staffing is a named gap. Never invent a person.
- **`## Velocity calibration protocol`:** state `velocity not calibrated`. Then define what the separately gated pilot measures and how measured actuals could later replace the forecast basis: person-hours per work class, review and QA time, rework and escaped defects. One pilot informs comparable work classes, not enterprise velocity. Never claim savings or a calibrated rate.

## Plan acceptance

Every work package links its scoped quantity, role and forecast effort to CSV, names client prerequisites, objective exit evidence, milestone, assumptions and status. The SOW cannot accept enterprise work beyond the demonstrated pilot. Keep assessment effort, pilot forecast and enterprise forecast distinct; actual pilot measurements use a separate evidence ledger. Changes in scope/owner/calendar require revised assumptions and a rerun of affected dependency/effort checks.

Start from [implementation-plan.md](../templates/implementation-plan.md). JSON/Markdown sample fields are Bob's responsibility to replace; a structurally valid graph cannot authorize a release or prove dates achievable.
