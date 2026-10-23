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
# Implementation plan — dependency-aware forecast

## Scope and source of effort

{{Link assessment.md finding IDs and the exact effort-model.csv hash. State one Java invoice-preview implementation boundary, assessment-only targets and enterprise forecast exclusions. List included/excluded low/central/high totals copied from deterministic validation; all monetary state is not priced.}}

## Delivery waves and work packages

| WBS ID / deliverable | Finding IDs | Owner role | Predecessors | Client input | Effort low / central / high hours | Relative duration / basis | Exit evidence / milestone | Assumption / status |
|---|---|---|---|---|---|---|---|---|
| {{WBS-ID / DEL-ID}} | {{F-IDs}} | {{role}} | {{WBS-IDs or none}} | {{dependency}} | {{exact CSV values}} | {{days / capacity basis}} | {{T-ID / gate}} | {{forecast / pending}} |

Describe waves for evidence closure, baseline capture, bounded pilot, independent verification, rollback rehearsal and later target decisions. Other target implementations remain forecast-only.

Finding disposition table (one row per accepted finding ID; keep each complete row on one line for deterministic reconciliation):

| Finding ID | Disposition | WBS IDs | Owner | Reason |
|---|---|---|---|---|
| {{F-ID}} | {{mapped / deferred / accepted_risk}} | {{complete WBS list or none}} | {{null for mapped; explicit role otherwise}} | {{null for mapped; explicit reason otherwise}} |

## Work packages by component

| WBS | Component | Owner role | Duration days | Effort basis |
|---|---|---|---|---|
| {{WBS-ID}} | {{module as named in the discovery map, or cross-cutting}} | {{role}} | {{plan-tasks duration_days}} | {{basis linked to findings and effort rows}} |

## Staffing and skills coverage

{{Synthetic roster read through the governed roster tools, or a named gap if unavailable. People are synthetic placeholders; assignments are proposals pending the resourcing owner.}}

| WBS | Required skills | Named synthetic people (SE-NN) | Availability window | Skills gap |
|---|---|---|---|---|
| {{WBS-ID}} | {{skills}} | {{SE-NN Synthetic Engineer NN}} | {{window from roster availability}} | {{gap and mitigation, or none found}} |

## Velocity calibration protocol

Velocity not calibrated. {{what the separately gated pilot measures per work class, how actuals are recorded and when they may replace the forecast basis}}

## Team, responsibilities and sign-offs

| Role | Accountable work / decision | Inputs supplied | Review or sign-off evidence | Separation / pending authority |
|---|---|---|---|---|
| {{Customer IT / SI architect / developer / senior developer / tech lead / QA / PM / commercial lead}} | {{bounded responsibility}} | {{artifact/access/decision}} | {{review record, commit/PR, ticket/wiki or T-ID}} | {{independence or unauthenticated role label}} |

## Critical dependency chain

{{Record validate_dag.py input hash, baseline output and critical chain. Distinguish labor hours from elapsed days; dates are relative or explicitly illustrative until client calendars are known.}}

## Prerequisite delay review

| Delayed prerequisite | Added elapsed days | Baseline dependent gate | Recomputed gate | Affected WBS IDs | Required owner response |
|---|---|---|---|---|---|
| {{WBS-ID}} | {{delay}} | {{baseline day}} | {{validated day}} | {{IDs}} | {{pending action}} |

## Acceptance, responsibilities and client inputs

{{Objective inspection methods and reviewer roles linked to sow.md; required environments, named seeds, owner decisions and evidence access. Approval stays pending; role labels are responsibilities rather than authenticated identities.}}

## Delivery controls and stakeholder visibility

{{Map WBS and finding IDs to Git branch/commit/PR checkpoints, synthetic Jira-style ticket IDs, wiki/decision records, status cadence, escalation path and evidence location. Distinguish simulated connector records from authenticated GitHub/Atlassian actions.}}

## Risks, exclusions and change control

{{List explicit uncertainty drivers; scope/calendar/rate changes trigger revised assumptions and rerun of dependency/effort checks. Show other targets as planning only. Preserve blocked work and NO-GO/pending gates.}}
