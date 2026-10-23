---
version: "{{artifact_version}}"
as_of: "{{as_of_date}}"
run_id: "{{run_id}}"
source_revision: "{{source_revision}}"
kit_version: "{{kit_version}}"
author: "IBM Bob"
status: pending
synthetic_demo: true
target: all
evidence: pending
scope: included
---
# Migration assessment — synthetic client draft

## Recommendation and decision

<!-- portal: target=all evidence=pending scope=included -->
Recommendation: {{decision and reason linked to finding IDs}}. Decision owner: {{human owner}}. Decision required: {{pending action}}. Blockers: {{finding/gap IDs}}. Evidence that could change the recommendation: {{named evidence and validation action}}.

Pilot boundary: {{one Java invoice-preview scope and exclusions}}. Overall gate: {{actual NO-GO / pending / accepted evidence}}. Production deployment, security clearance and enterprise performance: {{executed scope or not verified}}.

## Current state and inspected evidence

| Component / entry point | Source path or run | Evidence ID / class | Observed fact | Uncertainty / owner action |
|---|---|---|---|---|
| {{component}} | {{exact pointer}} | {{EV-ID / class}} | {{bounded observation}} | {{gap}} |

## Legacy code health and poor-practice findings

| Finding ID | Category | Observed condition and business/operational impact | Ordinal severity and rationale | Evidence IDs / class | Treatment / decision |
|---|---|---|---|---|---|
| {{F-ID}} | {{friendly display label backed by one exact JSON category value}} | {{bounded finding and why it matters}} | {{category / rationale}} | {{EV-IDs / source, test, runtime, interview, inference or unknown}} | {{retain, contain, refactor, migrate or validate first}} |

Cover every inspected category or state `not evidenced in supplied scope` with the corresponding gap. Never turn a static no-reference result into a dead-code claim.

Evidence disposition table (one row per accepted evidence ID; keep each complete row on one line for deterministic reconciliation):

| Evidence ID | Disposition | Finding IDs | Owner | Reason |
|---|---|---|---|---|
| {{EV-ID}} | {{mapped / deferred / accepted_risk}} | {{complete F-ID list or none}} | {{null for mapped; explicit role otherwise}} | {{null for mapped; explicit reason otherwise}} |

## Technical debt scoring (SI-measured, Bob-scored)

Metrics input: `runs/{{run_id}}/inputs/complexity-metrics.json` (SI-measured by `tools/metrics/complexity_metrics.py`; Bob measures nothing). Scoring rubric: {{score scale, which metrics move a score and how linked finding categories adjust it}}.

| Component | Source path | lines_code / method_count / max_method_branch_count | Score and rubric reason | Finding IDs / evidence IDs |
|---|---|---|---|---|
| {{component}} | {{path from the metrics input}} | {{values copied from the input or unknown}} | {{score / reason}} | {{F-IDs / EV-IDs}} |

Label: SI-measured, Bob-scored. {{what the metrics cannot show}}

## Architecture, dependencies and operations

| Dependency / call path / data flow | From → to | Evidence IDs / class | Operational consequence | Unknown and validation owner |
|---|---|---|---|---|
| {{dependency}} | {{entry point → service → data/job}} | {{EV-IDs / class}} | {{failure, coupling, deployment or recovery consequence}} | {{missing runtime/owner/volume/SLA/backup evidence and action}} |

## Operational history and ticket corroboration

{{Synthetic help-desk tickets and incidents read through the governed tickets tools, or a named gap if unavailable. Tickets are user reports, never diagnoses, and corroborate only.}}

| Ticket ID | Code-relevant? | Corroborates (finding with its primary EV- evidence on this line) | Limit |
|---|---|---|---|
| {{DESK-ID}} | {{yes / no and why}} | {{F-ID with EV-IDs, or none}} | {{user report; not a diagnosis}} |

## Security assessment

Review basis: source-reading review, no scanner. {{source scope read and what a scanner or dependency audit would still need to establish}}

| Finding ID | Defect/advisory/scan type | Component and affected-version state | Execution-path/reachability evidence | Status and remediation proof |
|---|---|---|---|---|
| {{F-ID}} | {{code, configuration, dependency match or scanner result}} | {{exact component / under investigation}} | {{EV-IDs or not tested}} | {{under investigation / evidence-backed stronger status}} |

## Options and target tradeoffs

{{Compare retain/contain, bounded migration and deeper modernization; link target-annexes.md and each relevant finding ID. State unexecuted feasibility as unknown.}}

## Modernisation options scoring

Scoring criteria: {{business criticality, technical fit, effort basis, delivery risk, reversibility; scale and evidence for each}}.

| Component | Business criticality (evidence or unknown + owner) | Selected path | Paths rejected with one-line reasons (retire, retain, rehost, relocate, repurchase, replatform, refactor) | Criteria scores | Finding IDs |
|---|---|---|---|---|---|
| {{component}} | {{rating / basis}} | {{path}} | {{each rejected path and reason}} | {{per criterion}} | {{F-IDs}} |

## Pilot actuals and future forecasts

| Metric | Observed pilot actual / future forecast | Value / unknown | Source run and revision | Limit |
|---|---|---|---|---|
| {{metric}} | {{classification}} | {{value or unknown}} | {{T-ID / source}} | {{untested scope}} |

## Effort, dependencies and unresolved inputs

{{Reference the exact effort-model.csv hash and scenario/role totals; do not recompute from prose. Link implementation-plan.md WBS and dependencies. Monetary state remains not priced without authorized rates/terms.}}

## Decisions, operational gaps and acceptance limits

| Decision / gap ID | Owner role | Client input / action | Blocks | Evidence that closes it |
|---|---|---|---|---|
| {{DEC/GAP-ID}} | {{owner}} | {{missing telemetry, owner interview, data volume, backup/DR, deployment or scan input}} | {{WBS / deliverable}} | {{objective check}} |

{{Reference validation-ledger.md for actual checks, original native response/task IDs and independently reviewed artifact versions.}}
