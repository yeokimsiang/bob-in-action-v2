# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## What this repo is

An IBM Bob SI assessment demo kit. Four slash commands drive Bob from discovery to SOW across nine persona modes. The legacy app (`app/`) is a deliberately flawed Java 8 Spring Boot invoice desk — read it; never modify it.

## Hard constraints

- **Bob has no shell.** `execute_command` and any `delete`/`move`/`rename` are blocked by `.bob/hooks/pre_tool_guard.py` (exit 2). Never claim a build or test ran unless the user pasted its actual output.
- **Bob writes only inside `runs/<name>/`.** Writes to `app/`, `tools/`, `targets/` or `.bob/` are refused by the hook guard.
- **One writer per file.** Never edit another persona's output or checker-rendered files (e.g. `effort-model.csv` belongs to `validate_effort.py`, not Bob).
- **Run name** must match `[A-Za-z0-9][A-Za-z0-9._-]*`.
- **`SI kit hooks active`** must appear in context at session start. If it does not, the guard is off — tell the user and write nothing until confirmed.

## Stage order and checker commands

Each stage runs in a specific mode and must follow the previous stage's checker passing.

| Stage | Mode | Bob writes |
|---|---|---|
| `/discover <name>` | `si-architect` | `runs/<name>/data/discovery-evidence.json` |
| `/assess <name>` | `si-architect` | `reports/assessment.md`, `reports/target-annexes.md`, `data/findings.json` |
| `/plan <name>` | `si-pm` | `reports/implementation-plan.md`, `reports/validation-ledger.md`, `data/plan-tasks.json` |
| `/price <name>` | `si-commercial` | `reports/sow.md`, `data/effort-rows.json` |

The user runs checkers from the repo root with `python` (must be 3.11+). If only `py` is available, `.bob/settings.json` and `.bob/mcp.json` must be updated to use `py`.

Checker tools that write files (`illustrative_price.py`, `check_effort_numbers.py`) refuse to overwrite — delete their outputs before re-running.

## Run folder layout

```
runs/<name>/
  inputs/   complexity-metrics.json (user writes, from tools/metrics/complexity_metrics.py)
  data/     discovery-evidence.json, findings.json, plan-tasks.json, effort-rows.json (Bob)
  reports/  assessment.md, target-annexes.md, implementation-plan.md, validation-ledger.md, sow.md (Bob); effort-model.csv (validate_effort.py)
  checks/   illustrative-price.json, effort-check.json (checker tools)
  pilot/    pilot-plan.json, candidate/ (si-developer persona)
```

## Global IDs and evidence conventions

- Use prefixed IDs: `EV-` (evidence), `REL-` (relationships), `F-` (findings), `WBS-` (work packages), `DEL-` (deliverables), `RD-` (risk drivers).
- `run_id` in every JSON = the run name. `source_revision` = value passed to `/discover` or literal `working-tree`.
- `kit_version` in reports = `kitVersion` from `.bob/kit-version.json`.
- Unknown values stay unknown — never invent zero or a placeholder.

## MCP servers (read-only, synthetic data)

Four mock servers: `roster`, `ratecard`, `tickets`, `timesheets`, all started as `python ${workspaceFolder}/tools/mcp/launch.py <server>`; their data is invented, so label it synthetic. A fifth, `checks` (`tools/checkers/checks_server.py`), runs a stage's README checkers on your own files and writes nothing. `alwaysAllow` is empty — Bob asks before every call.

Allowed MCP tools per mode:
- every writer mode: the `checks` tool (`run_stage_checks`) on its own stage's files, before it stops
- `si-architect`: tickets tools (`tickets_search`, `tickets_get`, `incidents_list`), and only during `/assess`
- `si-pm`: roster tools (`roster_list_people`, `roster_find_by_skill`, `roster_availability`)
- `si-commercial`: ratecard + roster + timesheets tools

## Legacy app (`app/`) key facts

- Spring Boot 2.7.18, Java 8, H2 in-file database, Maven
- Build: `.\app\Build.ps1` (requires JAVA8_HOME or JDK 8 at the default path; sets JAVA_HOME internally)
- Test: `mvn -B -ntp test` from `app/` (or `Build.ps1` which runs `clean verify`)
- Single test: `mvn -B -ntp -Dtest=DeskMoneyTest test` from `app/`
- App runs on port `${DEMO_PORT:18080}`, H2 stored in `./runtime/data/base`, date fixed to `demo.today=2026-10-13`
