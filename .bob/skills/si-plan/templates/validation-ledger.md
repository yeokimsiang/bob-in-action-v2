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
# Validation and provenance ledger

## Native origin and immutable artifacts

{{List the run name, source revision, kit version, the checker commands the user ran with their actual results, and artifact versions. Preserve rejected originals. Evaluator material is not part of the workspace and was not supplied to Bob; record evidence for separation rather than matching prose.}}

## Material claim-to-evidence map

| Finding / claim / test ID | Artifact / version | Evidence class | Exact path / command output / native run | Timestamp / revision | Scope / gap / owner |
|---|---|---|---|---|---|
| {{ID}} | {{artifact/version}} | {{class}} | {{pointer}} | {{actual metadata}} | {{limits}} |

## Executed checks and visible failures

| Test ID / assertions | Exact command | Exit / native error | Result / output pointer | Tested hashes | Untested scope |
|---|---|---|---|---|---|
| {{T-ID / assertions}} | {{command or not run}} | {{actual exit or unknown}} | {{pass / fail / not reviewed}} | {{source/artifact/contract/checker}} | {{gap}} |

## Numerical and dependency reconciliation

{{Record effort-model.csv hash, exact row/role/scenario totals, unpriced status, WBS/meaning crosswalk, baseline/delayed DAG outputs and SOW reconciliation. Unknown/stale rates and missing authority remain blockers.}}

Enumerate every accepted `EV-` evidence ID exactly once in this ledger's claim map or reconciliation text. The final gate rejects missing or invented evidence IDs.

## Adversarial rubric and gate

| Rubric / blocker ID | Actual artifact version | Ordinal score NR / 0 / 1 / 2 | Disproof attempt / evidence | Open correction |
|---|---|---|---|---|
| {{Q/B-ID}} | {{version}} | {{actual review score}} | {{check}} | {{pending action}} |

Record every active criterion ID and blocking-failure ID from `.bob/standards/report-quality-rubric.json` exactly once. Unreviewed criteria use `NR`; blockers use open/closed with evidence. The current standard includes Q01–Q15 and B01–B10, plus the factory v2 criteria Q16–Q21 and blockers B11–B13; that rubric file remains authoritative if versioned differently.

Gate: {{rejected / not reviewed / accepted from actual independent result}}. Decision owner: {{human role; pending if unauthenticated}}. No unrun check is a pass. A native limit/error rejects nominal success.

## Pilot observations, forecasts and rollback

{{State objective, changed boundary, legacy/target revisions, exact runtime/browser/API/full-table/control/rollback evidence, before/after behavior and failures. Separate observed pilot actuals from future forecasts; acknowledge unexecuted production/security/performance scope.}}

## Correction history

| Discrepancy ID | Original / corrected versions | Supporting evidence | Corrected source artifact | Rerun command / result / new hash |
|---|---|---|---|---|
| {{ID}} | {{versions}} | {{pointer}} | {{path}} | {{actual check or not reviewed}} |
