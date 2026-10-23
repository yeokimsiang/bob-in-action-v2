# Evidence and provenance

Substantive prose and pilot code are Bob-authored. Checkers calculate, validate and render; they must not silently repair reports. The one permitted normalization is `validate_findings.py --normalize-evidence-closure`: it mirrors a redundant evidence link Bob explicitly declared on one side of the finding/disposition relation to the other side, records every changed JSON path with before and after hashes, and then applies the unchanged strict check. It cannot invent IDs, alter prose or finding attributes, or resolve deferred or accepted-risk conflicts.

Bind findings, WBS items, citations and effort rows to one `run_id` (the run name) and one `source_revision`. Distinguish observed, inferred, assumed and unknown evidence. Preserve source paths, line pointers and revisions without secrets. A tool's success message is not acceptance. Unknown values stay unknown, never zero.

Use global IDs: `EV-` for evidence, `REL-` for relationships, `F-` for findings, `WBS-` for work packages, `DEL-` for deliverables, `RD-` for risk drivers. Exact arithmetic belongs to the checkers and the SI commercial engine. Missing approved rates keep the work unpriced; the synthetic rate card is illustrative and never a quote. Tests are behaviour evidence, not labour measurements. Keep NO-GO, TBD and human-pending states visible.

Follow the report standard in `.bob/standards/report-quality-standard.md` and the machine-reviewable rubric `.bob/standards/report-quality-rubric.json`. The finding and handoff schemas are in `.bob/schemas/`; they are custom SI contracts, not IBM report schemas.
