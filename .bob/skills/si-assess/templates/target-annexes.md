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
# Target-specific assessment annexes

Each annex links consolidated findings in assessment.md. Implementation is assessment/planning only except a separately authorized Java invoice-preview pilot. For every profile complete the three subsections below: decision/options; compatibility/behavior/evidence; and delivery/rollback/open decisions. Do not infer execution from prepared reference code.

## Java 8 → Java 21

<!-- portal: target=java21 evidence=pending scope=included -->
Profile: java-8-to-21

### Decision and options
{{Recommendation, retain/contain alternative, bounded-migration alternative, deeper-modernization alternative, decision trigger and F-IDs.}}

### Compatibility, behavior and evidence
{{Impacted legacy app components; runtime/build/library/API/data/browser invariants; exact EV-IDs; scoped feasibility checks and actual result or not run.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, sequencing/dependencies, rollback boundary, uncertainty, client input, pending owner and evidence that closes the decision.}}

## Java → Kotlin

<!-- portal: target=kotlin evidence=pending scope=included -->
Profile: java-to-kotlin

### Decision and options
{{Recommendation and alternatives linked to F-IDs; explain when interop migration is justified.}}

### Compatibility, behavior and evidence
{{Impacted components; Java/Kotlin interop, nullability, decimal/serialization and framework constraints; EV-IDs; feasibility checks are not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, increment boundary, rollback, uncertainty, client input and pending owner.}}

## JavaScript → TypeScript

<!-- portal: target=typescript evidence=pending scope=included -->
Profile: javascript-to-typescript

### Decision and options
{{Recommendation and strictness/increment options linked to F-IDs.}}

### Compatibility, behavior and evidence
{{Impacted frontend modules; browser/API contract, build tooling, third-party types and runtime validation; EV-IDs; feasibility checks are not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, module order, build rollback, uncertainty, client input and pending owner.}}

## H2 → PostgreSQL

<!-- portal: target=postgresql evidence=pending scope=included -->
Profile: h2-to-postgresql

### Decision and options
{{Recommendation and retain/replace/dual-run options linked to F-IDs.}}

### Compatibility, behavior and evidence
{{Impacted schema/queries/jobs; SQL dialect, types, identity, transactions, isolation and reconciliation invariants; EV-IDs; checks not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, migration/cutover/reconciliation gates, backup/restore rollback, volume/environment gaps and pending owner.}}

## Monolith → Preview microservice

<!-- portal: target=microservices evidence=pending scope=included -->
Profile: monolith-to-preview-service

### Decision and options
{{Recommendation and retain-module/extract-service alternatives linked to F-IDs.}}

### Compatibility, behavior and evidence
{{Boundary/call graph; contract, authentication, timeout, retry/fallback, idempotency, data ownership and observability; EV-IDs; checks not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, strangler/route sequence, route rollback, operational ownership gaps and pending owner.}}

## Java → Python / FastAPI

<!-- portal: target=fastapi evidence=pending scope=included -->
Profile: java-to-fastapi

### Decision and options
{{Recommendation and coexist/rewrite alternatives linked to F-IDs.}}

### Compatibility, behavior and evidence
{{Impacted endpoints/jobs; Decimal/JSON, noncoercing schemas, async behavior, persistence, transactions and packaging; EV-IDs; checks not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, route/data sequence, rollback, Python operating-model gaps and pending owner.}}

## Java → C# / ASP.NET Core

<!-- portal: target=aspnetcore evidence=pending scope=included -->
Profile: java-to-aspnet-core

### Decision and options
{{Recommendation and coexist/rewrite alternatives linked to F-IDs.}}

### Compatibility, behavior and evidence
{{Impacted endpoints/jobs; decimal/JSON, binding/overflow, middleware, persistence, transactions and hosting; EV-IDs; checks not run unless evidenced.}}

### Delivery, rollback and open decisions
{{WBS/effort basis, route/data sequence, rollback, .NET operating-model gaps and pending owner.}}
