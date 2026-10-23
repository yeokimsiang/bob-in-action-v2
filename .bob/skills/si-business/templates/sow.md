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
# Draft statement of work

**Draft—synthetic demonstration / nonbinding / unpriced.** Client approval, signature, rate, legal terms and acceptance are pending/TBD. This template establishes no authority or production migration commitment.

## Purpose, boundary and exclusions

{{State reviewed assessment purpose and one Java invoice-preview pilot boundary. Exclude other-target implementation, untested enterprise/production work, unsupported security/performance claims and paid/live integrations. Link assessment finding IDs.}}

## Deliverables and artifact crosswalk

| Deliverable ID | Exact source artifact | WBS / finding IDs | Included scope | Objective inspection method | Reviewer role |
|---|---|---|---|---|---|
| {{DEL-ID}} | assessment.md | {{IDs}} | {{scope}} | {{traceability/rubric check}} | {{role}} |
| {{DEL-ID}} | target-annexes.md | {{IDs}} | {{assessment only}} | {{profile coverage check}} | {{role}} |
| {{DEL-ID}} | effort-model.csv | {{IDs}} | {{forecast}} | {{exact Decimal totals/hash}} | {{role}} |
| {{DEL-ID}} | implementation-plan.md | {{IDs}} | {{forecast gates}} | {{dependency/delay check}} | {{role}} |
| {{DEL-ID}} | sow.md | {{IDs}} | {{unpriced draft}} | {{scope/ID/terms reconciliation}} | {{role}} |
| {{DEL-ID}} | validation-ledger.md | {{IDs}} | {{actual evidence}} | {{run/hash/check inspection}} | {{role}} |

Finding disposition table (one row per accepted finding ID; keep each complete row on one line and match the validated plan sidecar):

| Finding ID | Disposition | WBS IDs | Owner | Reason |
|---|---|---|---|---|
| {{F-ID}} | {{mapped / deferred / accepted_risk}} | {{complete WBS list or none}} | {{null for mapped; explicit role otherwise}} | {{null for mapped; explicit reason otherwise}} |

## Effort and relative schedule

{{Use the exact included/excluded low/central/high CSV totals and CSV hash. Monetary fields remain not priced. Reference implementation-plan.md dependencies, milestones, duration basis and client calendar uncertainty. Bobcoin usage is separately measured inference usage, not delivery price.}}

## Rate-card roles and risk drivers

{{Roles and the risk-allowance assumption read through the governed rate-card tools, or a named gap if unavailable. No rates, amounts or arithmetic appear here.}}

| Effort role | Rate-card role or no rate-card role | Basis for the mapping | Risk drivers chosen (assumption ID, no amount) |
|---|---|---|---|
| {{exact role text from effort rows}} | {{rate-card role name}} | {{why}} | {{driver / assumption ID}} |

## Risk drivers

| ID | Risk driver | Likelihood | Hours impact | Affects |
|---|---|---|---|---|
| {{RD-01}} | {{short phrase naming the risk}} | {{Low, Medium or High}} | {{positive whole number of extra hours}} | {{WBS IDs from the effort rows, comma-separated}} |

{{Synthetic pilot variance note in words, from the governed timesheets tools: over or under plan, on which kinds of work, and how it shaped the drivers. No figure, ratio or percentage; the engine computes the calibration. No text between the heading and the table.}}

## Illustrative price reference

{{After this stage the SI commercial engine calculates an illustrative, synthetic price table from the validated effort-model.csv and the rate card (pricing_status: illustrative). State that it is not a quote, carries no approval, and that check_effort_numbers.py cross-checks every figure. Reference it; reproduce no figure.}}

## Responsibilities and client dependencies

| Owner role | Responsibility | Required input / environment | Dependency WBS | Evidence of readiness |
|---|---|---|---|---|
| {{SI/client role}} | {{work}} | {{source, access, seeds, owner decision, calendar}} | {{WBS-ID}} | {{EV/T-ID or pending}} |

## Review, correction and acceptance

Reviewer role: {{authorized human role}}. Review window: {{proposed relative window; pending agreement}}. Inspection: {{objective agreed assertions and evidence}}. Correction cycle: {{proposed bounded cycle, version preservation and rerun checks}}. Acceptance status: **pending**. Passing a prepared test or native Bob result does not supply a human signature.

## Change control and commercial terms

{{Scope, environment, calendar, acceptance, rate or law changes require a documented request, impact/WBS revision and authorized human decision before expansion.}} Price: **not priced**. Currency/tax/expenses, payment, liability, governing law and signatures: **TBD / pending authorized review**.
