---
name: si-delivery-control
description: Maintains migration work-package traceability through Git, tickets and wiki records. Use when tracking implementation, preparing a PR packet or updating delivery documentation.
---

# si-delivery-control

Custom SI workflow, not an IBM premium package.

Use one correlation chain finding -> WBS/ticket -> branch/commit -> PR/review -> tests -> rollback -> wiki. Local simulator is synthetic and is not Atlassian. MCP tool discovery and successful readback prove only that connector action. Default read-only; writes require run scope and confirmed record revision. Never invent approval or assignees. Git pull only for a known remote with inspected divergence; no forced destructive operations. PR author and reviewer need actual separate credentials; AI review does not replace human acceptance. Keep a published repository free of evaluator answers, secrets and runtime data.

Record every native event and metered result. A final nominal success does not override an earlier cost-limit, turn-limit or error event. Preserve rejected partial work under its run ID, do not promote it, and start a separately budgeted correction only from explicit review findings. Require a clean allowlisted `bob:` commit after tests; no commit, dirty state, generated artifacts or missing evidence means the implementation gate remains open.

For multi-file reports, distinguish response generation from file mutation before spending: Ask mode may return an envelope but must not be assigned file-writing acceptance; Agent mode writes files. Prepopulate a versioned Bob-authored starting pack, give each file an explicit correction checklist, use bounded in-place edits and verify each expected diff. A native limit or any missing expected file diff rejects the whole candidate. Never assemble untouched and partial files into an accepted pack.

Honor the report-quality standard in `.bob/standards/`. Preserve authorship and unresolved decisions.
