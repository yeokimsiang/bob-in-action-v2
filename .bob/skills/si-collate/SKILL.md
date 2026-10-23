---
name: si-collate
description: Checks a run's six-file migration assessment pack for completeness and cross-file traceability. Use when deciding whether a pack is ready for review or which report blocks it.
---

# Report-pack completeness check

Custom SI packaging asset. Bob's original reports supply meaning; the deterministic checker hashes and validates them unchanged at zero Bob credits. The `si-collator` persona is read-only inspection: it never authors recommendations or commercial prose, runs nothing and publishes nothing.

1. The pack is `runs/<name>/reports/` and must hold exactly the six files: `assessment.md`, `target-annexes.md`, `implementation-plan.md`, `validation-ledger.md`, `sow.md` and `effort-model.csv`.
2. **Checker (the user runs it; Bob has no shell):** the client-pack completeness and cross-file traceability [quality checker](scripts/validate_report_quality.py), Python 3.11+, from the repository root:

   `python .bob/skills/si-collate/scripts/validate_report_quality.py --pack runs/<name>/reports --rubric .bob/standards/report-quality-rubric.json --findings runs/<name>/data/findings.json --plan-tasks runs/<name>/data/plan-tasks.json --effort-rows runs/<name>/data/effort-rows.json`

   This rejects unresolved templates, missing report sections, incomplete seven-target/rubric coverage, and WBS/deliverable drift. It also runs these section checks, in this order after the eight completeness checks:
   - SI-measured, Bob-scored debt scoring;
   - seven-path option scoring with business criticality;
   - ticket corroboration only;
   - "source-reading review, no scanner" wording;
   - per-module work packages;
   - roster staffing with skills gaps;
   - the velocity calibration protocol;
   - rate-card role mapping;
   - the not-a-quote illustrative price reference;
   - no currency amounts in Bob's prose.

   Exit 0 still leaves semantic review pending: it does not prove claims, estimate reasonableness or human approval.

   A partial mode runs right after Assess and right after Plan, so a section failure can be corrected in that stage instead of waiting for the final check:

   `python .bob/skills/si-collate/scripts/validate_report_quality.py --partial-stage assess --pack runs/<name>/reports --findings runs/<name>/data/findings.json`

   `python .bob/skills/si-collate/scripts/validate_report_quality.py --partial-stage plan --pack runs/<name>/reports --findings runs/<name>/data/findings.json --plan-tasks runs/<name>/data/plan-tasks.json --rubric .bob/standards/report-quality-rubric.json`

   It runs every final-check rule whose inputs exist after that stage, on that stage's own reports: headings, placeholders, front matter, the evidence and finding ID closure and disposition rows, and the stage's section checks (Assess also checks the seven annex blocks; Plan also checks the ledger's evidence IDs and rubric record). It applies the same rules as the final check and never replaces it.
3. A blocked pack returns to the persona that wrote the failing file, with the checker's exact error; no silent correction is allowed. Keep evaluator material, held-out answers and secrets outside all inputs; external publication needs separate human authorization.
