---
name: si-code-review
description: Reviews migration changes and repairs substantiated defects without inventing acceptance. Use when reviewing a pilot diff, coding principles or reviewer feedback.
---

# si-code-review

Custom SI workflow, not an IBM premium package.

Review exact candidate revision and tests, contract boundaries, money types/rounding, transactions, concurrency, input errors, SQL parameters, secrets and useful documentation. Link each issue to evidence and an actionable correction. Preserve Bob original output, revise separately and rerun affected checks. Model agreement is supporting review, not ground truth or human signoff. Another stage or tool must execute the independent acceptance checks.

For a pilot, write the exact [revision-bound review template](templates/pilot-review.json) to `runs/<name>/pilot/pilot-review.json`. Any P0/P1/P2 finding or non-pass verdict blocks QA verification and acceptance.

Challenge green tests by tracing untested trust boundaries. For JSON/HTTP migrations, inspect parser coercion, exact integer conversion, media matching, body/response byte limits, redirects, loopback pinning, connection cleanup, complete identifier/type/scale comparisons and independent arithmetic recomputation. Probe one plausible forged success and one overflow value. Review build packaging and generated files as well as source; a compiler pass does not prove the executable name, runtime JVM, database isolation, process ownership or rollback.

Honor the report-quality standard in `.bob/standards/`. Preserve authorship and unresolved decisions.
