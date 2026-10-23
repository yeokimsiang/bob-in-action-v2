# Effort and SOW contract

Read this before estimating, reconciling or correcting the commercial artifacts. The authoritative structured commercial snapshot and its exporter schema/validation/hash take precedence over prose; [the evidence hierarchy](../evidence-contract.md) explains origin and approval limits.

## Exact WBS interface

Use the existing 15 string fields in order:

`deliverable_id,wbs_id,task_name,role,quantity,unit,low_hours,central_hours,high_hours,method,evidence_or_comparable,uncertainty_driver,included,status,notes`

[effort-rows.json](../templates/effort-rows.json) is the callable helper input object with only `rows`. Each row is an exact 15-field object; fields are at most 500 characters, all except `notes` are nonempty. WBS IDs are unique `WBS-1.1` forms. Numeric strings are nonnegative finite decimals (up to 12 whole and 6 fractional digits), and low ≤ central ≤ high. `included` is exactly `included` or `excluded`; `status` is `forecast`, `assessment-forecast`, `pilot-future-forecast` or `future-forecast`. Forecasts never use `actual`, `excluded` or prose as status. Text fields reject spreadsheet-formula prefixes. [effort-model.csv](../templates/effort-model.csv) demonstrates the header and one clearly synthetic unpriced row, without pretending its totals are an accepted pack.

Hours are total person-hours **per row**, not quantity multipliers. Quantity/unit describe scoped work; explain the quantity's estimate basis in `method`. Keep assessment forecasts, pilot forecasts, enterprise forecasts and separately evidenced pilot actuals apart. Never infer labor measurement from passing tests or reference construction.

[validate_effort.py](../scripts/validate_effort.py) calls the existing repository Decimal formatter, preserving RFC 4180 CRLF CSV, exact hash, included/excluded scenario totals, role totals and summary rows. This wrapper intentionally does not duplicate the existing arithmetic. An isolated run deploys the same trusted formatter and supplies `--formatter`; a missing module means numerical verification pending, not invented totals. Optional `--csv-output` creates a new authorized output only and refuses overwrite. It never rewrites Bob's report prose or revises estimates. The formatter/tool output is the sole numeric source copied into assessment, plan, SOW and ledger.

## Commercial decision controls

Require source revision, effective rate date, currency, rate approval basis, tax/expense treatment, inclusions/exclusions and real human authority before pricing. Synthetic demo rates support only a labelled illustrative scenario. Exporter schema 2 requires inspected `approval_trust` and `commercial_authorization.client_quote_allowed`; false blocks a client quote even if `calculation_status` says calculated or `pricing_status` conditional. Missing trust controls, conflicting/stale inputs or unknown schemas cannot authorize a quote. Preserve gaps and remain unpriced. Local asserted actor labels are not authenticated approval. Keep Bobcoin usage in its own actual-unit ledger, never as SI price.

Document uncertainty drivers separately from explicit allowances. Do not double-count ranged effort plus arbitrary buffer; no confidence percentiles, productivity savings or multipliers without measured support. One preview pilot can inform comparable work classes, not enterprise velocity. Elapsed schedule needs predecessor, capacity and calendar evidence.

## Factory v2 rate-card roles and illustrative price

The SOW may reference an illustrative, synthetic SGD price table calculated by the SI commercial engine (`pricing_status: illustrative`). The table is labelled "not a quote".

- **Roles:** each effort row's `role` is an exact rate-card role name returned by the `ratecard_roles` tool. When none fits, `role` is the SI role followed by `(no rate-card role)`, and `notes` says why. The 15-field row contract does not change.
- **Risk drivers:** Bob selects qualitative drivers against the rate card's risk-allowance assumption and cites that assumption's ID, never a percentage-derived amount. Bob also names each driver in a `## Risk drivers` table with a likelihood (`Low`, `Medium` or `High`), a whole-number hours impact and the affected WBS IDs. The SI engine weights those judgements; Bob calculates nothing from them.
- **Pilot variance:** Bob reads the synthetic pilot timesheets through the timesheets tools and writes a short variance note in words under the risk-driver table. The engine computes the calibration factor from the timesheets.
- **No Bob arithmetic:**
  - Bob never multiplies rates by hours, never applies the allowance, and never writes a currency amount in any report.
  - The engine calculates the table from the validated `effort-model.csv` after the price stage (`tools/checkers/illustrative_price.py`).
  - The SI runs `tools/checkers/check_effort_numbers.py --csv <effort-model.csv> --output <check.json> --sow <sow.md> --price-table <table>` to cross-check every figure. It rejects any number in the SOW's two commercial sections that the engine table does not hold, so those sections carry no numerals except inside identifiers or ISO dates.
  - The report-quality check rejects currency amounts in Bob's Markdown.
- **SOW sections:**
  - `## Rate-card roles and risk drivers` puts each distinct effort role, as exact text, in its own table cell, with its mapping, the basis for it and the chosen drivers.
  - `## Illustrative price reference` names the engine table, states "not a quote" and no approval, and names `check_effort_numbers.py`. It reproduces no figure.
  - `## Risk drivers` is its own section. Its first content is the table `| ID | Risk driver | Likelihood | Hours impact | Affects |`, one `RD-01`-style row per driver, followed by the pilot variance note. A malformed table fails the price gate closed.

## SOW and correction

[sow.md](../templates/sow.md) carries `Draft—synthetic demonstration / nonbinding / unpriced`. It links six artifact names, WBS/deliverable meanings, exact effort totals/hash, plan gates and objective pilot inspection evidence. It repeats every validated finding disposition on one complete table row: mapped findings name the exact WBS list; deferred or accepted-risk findings name owner and reason. This is traceability, not proof that a client accepted risk. Define reviewer role, review window, correction cycle, client inputs, exclusions and change-control triggers. Approval, signature, acceptance, legal terms and price stay pending/TBD absent authorized human evidence. The accepted boundary cannot exceed the demonstrated pilot.

If a reviewer finds a discrepancy, retain original native Bob output, identify artifact/version/evidence, edit only the authorized correction version, rerun affected numerical/traceability checks and update the ledger. Treat native limit/error events as rejected partial output even if Bob's final status says success. No cross-file ID collision or semantic support check is implied by CSV validation.
