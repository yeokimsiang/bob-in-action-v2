# Target profiles

Read only the selected rows' compatibility focus, then return to the [assessment contract](assessment-contract.md). These are custom SI routing notes, not IBM premium workflows. Each target annex stays an assessment: no target is migrated by this stage, and unexecuted feasibility stays unknown. Worked examples of each migration, built outside this kit, sit under `targets/<folder>/` for reference only.

| Target | Example folder | Compatibility focus / planned evidence |
|---|---|---|
| Java 21 | `targets/java/` | Actual JDK/runtime/build tooling and Jakarta compatibility; preserve preview/save thresholds, decimal serialization, API/browser/data/unaffected/rollback checks. The only candidate for the separately gated pilot. |
| Kotlin | `targets/kotlin/` | Java interop, nullability and decimal semantics; characterize identical contracts and job/config integration before rewriting. |
| TypeScript | `targets/typescript/` | Browser/build integration, static types plus runtime validation; retain DOM/API behavior and reject coerced/overflow inputs. |
| PostgreSQL | `targets/postgresql/` | H2-specific SQL/date functions, IDs, decimals, transactions, collation/timezones and full-table reconciliation; data rollback requires independently evidenced snapshots. |
| Microservices | `targets/microservices/` | Preview extraction, bidirectional schema validation, identifier/arithmetic checks, timeout/fallback, port/process ownership and unchanged persisted state. |
| Python (FastAPI) | `targets/python/` | Python Decimal/string-money and noncoercing request/response rules; transactional/persistence/job contracts and HTTP negative probes. |
| .NET (ASP.NET Core) | `targets/dotnet/` | C# decimal rounding/serialization, model binding/overflow, SQL/job behavior and runtime/API/browser equivalence scope. |

The focus column is a minimum; the agreed public behavior contract controls exact assertions and expected values. Link every target annex back to consolidated finding IDs. No row authorizes an AI-service enhancement.
