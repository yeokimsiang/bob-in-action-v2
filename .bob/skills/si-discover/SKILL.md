---
name: si-discover
description: Maps legacy source, routes, configuration and operational dependencies. Use when discovering an inherited application before a migration assessment.
---

# Evidence-led discovery

Custom SI asset using vanilla Bob. Work only on source inside the workspace (`app/`). Do not read evaluator-only folders or credentials, or edit application code.

1. Read the report standard in `.bob/standards/report-quality-standard.md` and the [discovery contract](references/discovery-contract.md). Inspect the exact cited source lines before recording a finding, following entry points through HTTP, SQL, scheduled/reflected jobs and browser call paths. [build_source_inventory.py](scripts/build_source_inventory.py) can print a compact static index of a source root for the user (`python .bob/skills/si-discover/scripts/build_source_inventory.py --root app`); it reduces repetitive reads but does not prove runtime usage.
2. Record observations and evidence-linked dependency/call-graph relationships in [evidence-map.json](templates/evidence-map.json), written to `runs/<name>/data/discovery-evidence.json`. The sample is synthetic training data; replace it with inspected evidence and preserve each evidence class. Mark every relationship observed, source-inferred or unknown. Carry missing telemetry, owner, volume and backup/DR inputs as named gaps.
   Depth: every cited `.java`/`.js` file gets one evidence row whose observation starts `Documentation note (<Component>):`, and material calls become `call` edges between `Class.method` names whose cited `path:line` literally contains the callee. Each `call` edge cites a dedicated call-site evidence row (one per call site) whose pointer is the exact call line or range and whose observation quotes that line verbatim in backticks; never a `Documentation note` row, a method declaration line (unless the call sits on it), a class header or line 1. Reflective/config dispatch cites the `job.execute(this)` invocation line, and only classes `jobs.properties` maps get an edge; an unmapped class is recorded as unwired, with no `call` edge. Before writing, re-read every cited call-site line range and confirm the callee name appears on it. Ticket records, if a later stage records any, use pointer `mcp:tickets/<id>`, class `interview` or `unknown` and a gap: they are user reports, not diagnoses.
3. **Checker (the user runs it; Bob has no shell):** after Bob writes the evidence map, the user runs [normalize_evidence.py](scripts/normalize_evidence.py) with Python 3.11+ from the repository root:

   `python .bob/skills/si-discover/scripts/normalize_evidence.py --input runs/<name>/data/discovery-evidence.json --source-root .`

   Input is the JSON template shape; stdout is sorted JSON plus the original input hash. Exit 0 checks structure; exit 2 rejects invalid input. With `--source-root` it also confirms that each code file has a documentation note, at least one method-level call edge exists, and every edge's cited file, line range and both method names exist in the source. It writes no files and cannot prove an observation true. When the user pastes errors, correct only the rows they name.
4. Hand the evidence map and explicit uncertainties to `si-assess`; human/runtime uncertainty prevents a static “dead code” conclusion. Preserve the quantity-100 preview/save discrepancy as published behavior.
