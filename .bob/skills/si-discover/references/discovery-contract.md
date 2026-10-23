# Discovery contract

Read this when mapping the estate. Bob supplies the observations and exact citations; the helper only checks and sorts them.

## Inspection order

Trace one complete browser-to-database path before expanding the inventory. Record controllers/routes, service calls, money calculations, data types, JDBC schema and SQL, properties, reflection registrations, scheduled/manual jobs and operations scripts. Check configuration and generated call sites before describing a component as “not referenced by inspected paths.” Removal still needs runtime/owner uncertainty resolved. Preserve the published preview/save threshold discrepancy; discovery cannot fix business behavior.

Use a stable `EV-` ID for each material observation. A pointer is an exact path with line/method, archived command output, native run/event, or documented stakeholder record. A build/test record additionally names the executed command, timestamp and source revision; an interview identifies the recorded assertion and owner without inventing consent or approval.

## JSON input

[evidence-map.json](../templates/evidence-map.json) has `schema_version: 1`, nonempty `run_id`/`source_revision`, an `evidence` array and a dependency/call-graph `relationships` array. Every evidence row has `id`, `class`, `pointer`, `observation` and `gap`; other provenance fields are preserved unchanged. Classes are `source_config`, `build_test`, `runtime`, `interview`, `inference` and `unknown`. Inference/unknown requires an explicit nonempty gap. Source inspection never upgrades to runtime merely because a path looks executable.

Every relationship has a stable `REL-` ID, `from_component`, `to_component`, `kind`, resolving `evidence_ids`, `runtime_status` and `gap`. Kinds are `http`, `call`, `sql`, `schedule`, `config`, `data`, `queue`, `file` or `unknown`. Runtime status is `observed`, `source_inferred` or `unknown`; the latter two require a gap and named validation need. Use component names that remain stable in assessment diagrams. A relationship is an evidence-linked edge, not proof of production frequency or completeness.

[normalize_evidence.py](../scripts/normalize_evidence.py) rejects duplicate IDs, empty pointers, unsupported classes, missing graph edges and unresolved relationship evidence. Exit 0 means a usable structural evidence index, with `semantic_review: pending`; it does not verify call completeness, source truth, production topology or owner intent. Exit 2 supplies JSON `errors`; retain the failure and correct the source input before retrying.

## Factory v2 depth

Documentation notes and method-level call edges live inside the same five-field schema; no new field is added.

- **Documentation note:** one `source_config` evidence row per cited `.java` or `.js` file. Its `observation` starts `Documentation note (<Component>):` and states what comments, Javadoc and names tell a maintainer and what stays undocumented. Its `pointer` is that file plus a line.
- **Method-level call edge:** a `call` relationship whose `from_component` and `to_component` are `Class.method` names (`desk.functionName` for `static/desk.js`; an optional `()` suffix is accepted). At least one cited evidence row has an exact call-site pointer `path:line` or `path:start-end` whose lines literally contain the callee method name. Keep coarser component edges too.
- **Call-site evidence:** each `call` edge cites a dedicated call-site evidence row, one per call site, whose pointer is the exact line or range holding the call expression and whose observation quotes that line verbatim in backticks. Never cite a `Documentation note` row, a method declaration line (unless the call sits on that same line), a class header or line 1. Reflective or config dispatch (`jobs.properties` -> `Class.forName(...)` -> `job.execute(this)`) cites the `job.execute(this)` invocation line plus the mapping row, and only classes `jobs.properties` maps get an edge; an unmapped class gets no `call` edge and is recorded as unwired in evidence. Before writing, re-read every cited call-site line range and confirm the callee name appears on it. The source check cannot tell a mapped class from an unmapped one, so this rule is Bob's to keep.
- **Source check:** `normalize_evidence.py --source-root <workspace>` rejects a pointer that escapes the root or names a missing file, a line outside the file, an undeclared caller or callee, a call site that does not mention the callee, a code file without a documentation note, and a map with no method-level edge. A passing check proves the cited lines exist, not that the edge list is complete.
- **Tickets:** a ticket or incident is a user report, never a diagnosis. Any evidence row that records one uses pointer `mcp:tickets/<id>`, class `interview` or `unknown` and a nonempty gap; the normalizer rejects other classes, and the findings validator rejects a finding that rests only on such rows.

## Handoff

Return run/source identity, the original map, normalized map/hash, inspected entry-point inventory, and gaps with an owner/action. Missing production telemetry, real data volumes, service levels, backup/DR results, security scans and deployment access are disclosed gaps rather than zero-risk claims. The report author links findings to these evidence IDs.
